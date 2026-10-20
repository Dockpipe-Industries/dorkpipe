const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { Readable } = require("node:stream");
const test = require("node:test");
const vm = require("node:vm");

const proxyPath = path.join(__dirname, "../resolvers/dorkpipe/assets/scripts/mcp-proxy.js");
const proxySource = fs.readFileSync(proxyPath, "utf8");

function createProxy(fetchImplementation) {
  let requestHandler;
  const diagnostics = [];
  const dependencies = {
    http: {
      createServer(handler) {
        requestHandler = handler;
        return { listen() {} };
      },
    },
    fs: {
      readFileSync() {
        return "synthetic-test-api-key";
      },
    },
  };

  vm.runInNewContext(proxySource, {
    require(name) {
      assert.ok(Object.hasOwn(dependencies, name), `Unexpected dependency: ${name}`);
      return dependencies[name];
    },
    Buffer,
    process: {
      env: {
        MCP_HTTP_API_KEY_FILE: "/synthetic/key",
        DORKPIPE_MCP_UPSTREAM_URL: "https://upstream.invalid",
      },
    },
    console: {
      error(...arguments_) {
        diagnostics.push(arguments_);
      },
    },
    fetch: fetchImplementation,
  }, { filename: proxyPath });

  return { requestHandler, diagnostics };
}

async function invokeProxy(proxy, url = "/") {
  const request = Readable.from([Buffer.from("request body")]);
  request.url = url;
  request.method = "POST";
  request.headers = { "content-type": "application/json" };
  const response = {
    headers: {},
    setHeader(name, value) {
      this.headers[name] = value;
    },
    end(body) {
      this.body = body;
    },
  };
  await proxy.requestHandler(request, response);
  return response;
}

function assertSanitizedFailure(response, diagnostics, failure) {
  assert.equal(response.statusCode, 502);
  assert.equal(response.headers["Content-Type"], "application/json");
  assert.deepEqual(JSON.parse(response.body), {
    error: "proxy_error",
    message: "The upstream MCP request failed.",
  });
  assert.equal(diagnostics.length, 1);
  assert.equal(diagnostics[0][0], "dorkpipe-mcp-proxy: upstream request failed");
  assert.equal(diagnostics[0][1], failure);
}

test("upstream exceptions remain in server diagnostics, not the public response", async () => {
  const failure = new Error("Private upstream details: /private/keys/mcp.pem");
  const proxy = createProxy(async () => {
    throw failure;
  });

  assertSanitizedFailure(await invokeProxy(proxy), proxy.diagnostics, failure);
});

test("non-Error failures also receive a stable public response", async () => {
  const failure = "Private upstream details: internal-node.invalid";
  const proxy = createProxy(async () => {
    throw failure;
  });

  assertSanitizedFailure(await invokeProxy(proxy), proxy.diagnostics, failure);
});

test("upstream body-read failures do not expose diagnostics", async () => {
  const failure = new Error("Private body-read diagnostics");
  const proxy = createProxy(async () => ({
    status: 200,
    headers: { get: () => "text/plain" },
    async text() {
      throw failure;
    },
  }));

  assertSanitizedFailure(await invokeProxy(proxy), proxy.diagnostics, failure);
});

test("successful requests preserve upstream status, content type, body and authentication", async () => {
  const proxy = createProxy(async (url, options) => {
    assert.equal(url, "https://upstream.invalid/mcp");
    assert.equal(options.method, "POST");
    assert.equal(options.headers.Authorization, "Bearer synthetic-test-api-key");
    assert.equal(options.headers["Content-Type"], "application/json");
    assert.equal(options.body.toString(), "request body");
    return {
      status: 202,
      headers: { get: () => "application/json" },
      text: async () => '{"result":"accepted"}',
    };
  });

  const response = await invokeProxy(proxy);
  assert.equal(response.statusCode, 202);
  assert.equal(response.headers["Content-Type"], "application/json");
  assert.equal(response.body, '{"result":"accepted"}');
  assert.equal(proxy.diagnostics.length, 0);
});
