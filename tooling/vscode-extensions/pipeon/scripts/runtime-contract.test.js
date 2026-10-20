const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs.readFileSync(path.join(__dirname, "../src/extension.ts"), "utf8");
assert(source.includes('"__state", "package-runtime"'), "The extension must use the package runtime scope");
assert(!source.includes('bin", ".dockpipe", "packages", "pipeon", "pipeon-context.md'),
  "The extension must not restore the legacy context-state fallback");
console.log("Editor package-runtime contract OK");
