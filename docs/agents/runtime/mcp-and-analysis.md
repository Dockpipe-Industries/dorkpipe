# MCP and analysis artifacts

The existing MCP bridge belongs to `packages/dorkpipe-mcp`. Read its
[package contract](../../../packages/dorkpipe-mcp/README.md) and
[bridge guide](../../../packages/dorkpipe-mcp/mcpbridge/README.md) before changes.
Dockpipe's proposed unified gateway remains a separate core backlog.

## Existing access tiers

`DOCKPIPE_MCP_TIER` selects `readonly`, `validate` or `exec`. An explicit tier
is authoritative. Without it, the legacy `DOCKPIPE_MCP_ALLOW_EXEC=1` enables
`exec`; otherwise the default is `validate`. Invalid explicit values fall back
to `validate`. HTTP keys can have their own bounded tier policy; inspect the
actual transport and key configuration before claiming a tool is available.

| Tier | Tool access |
| --- | --- |
| `readonly` | Listing and reading |
| `validate` | Read and validation; no run tools |
| `exec` | Run tools may be enabled, subject to their operation policy |

Tool availability does not grant permission to mutate an unrelated resource.
Preserve transport authentication, cancellation, error reporting and scoped access.

## Analysis artifacts

Treat self-analysis reports and generated handoff sections as dated evidence.
Compare their source identity with the work being reviewed; do not silently
refresh a generated analysis store or treat an old handoff as fresh authority.
Use explicit installed/source template paths: a historical template name alone
does not establish that `dockpipe init --from` can resolve it.

Generic artifact scopes and freshness rules remain in
[Dockpipe guidance](https://github.com/Dockpipe-Industries/dockpipe/blob/master/docs/agents/runtime/artifacts-and-mcp.md).
