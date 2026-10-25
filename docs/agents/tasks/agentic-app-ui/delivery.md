## Ownership Correction — 2026-10-17

Repository ownership note: package paths in this record describe external source. Current catalog packages live in [dockpipe-packages](https://github.com/Dockpipe-Industries/dockpipe-packages/tree/master/packages); previously extracted [DorkPipe/MCP](https://github.com/Dockpipe-Industries/dorkpipe/tree/master/packages) and [Pipeon](https://github.com/Dockpipe-Industries/pipeon/tree/master/packages/pipeon) remain in their own repositories. Historical paths and receipts do not recreate a local package tree.

DorkPipe owns the AI features and their delivery. The earlier separate DockPipe AI
package/app plan below is superseded wherever it conflicts with the
[active ownership decision](overview.md#product-naming-and-ownership).
Implement package-contributed views in the existing DockPipe app, shared CLI/API
operations and tools through TASK-039. No separate manifest identity, launcher app
or mandatory local container/service stack is required. Preserve existing generic
launcher work and historical proof; remote/mobile surfaces are optional future scope.

## Prioritized Delivery (not implemented)

1. Audit and deliver shared core foundations first: TASK-043 effective networking,
   ingress/egress/proxy configuration and verified backend guarantees, alongside
   exact-version package selection/lifecycle needed by all consumers.
2. Establish TASK-039's unified MCP and smallest generic contribution seams for
   package commands, existing-app views and tools. Preserve headless use.
3. Deliver DorkPipe DORK-001 knowledge ingestion/search, graphs/DAGs and context
   through those contracts, including MCP-routed retrieval from a minimal AGENTS
   bootstrap. Full-text search and explicit graph operations need no inference.
4. Keep skills management (DORK-002), chat, Models UI, richer AI authoring, editor consolidation and remote/mobile
   presentation deferred. They do not gate the core/MCP/knowledge release path.

Build in bounded slices after the direction audit. Core-first does not require every
future networking backend to be implemented before local MCP/knowledge qualification;
qualify the guarantees needed by each target deployment without silent fallback.

DORK-001 remains the authoritative knowledge backlog in the extracted DorkPipe repository;
this sequence coordinates integration and does not duplicate its implementation scope.

## Preserved Pipeon Interim Direct-Agent Slice (paused)

Pipeon is hidden and paused. The following previous design is retained for reference;
it does not authorize more Pipeon product work or block DorkPipe integration:

- Chat: provider/model-selectable direct chatbot for lightweight questions, local commands, and
  handoff.
- Codex chat: host `codex exec` with workspace sandboxing, host config model selection by
  default, and per-Pipeon-session transcript resume.
- Claude chat: guarded DorkPipe sandbox gate only; do not run raw Claude directly from chat.
- Workflow: `/workflow <name>` or generated workflow YAML for agentic work, including model lanes,
  multiple workers, approvals, verification, artifacts, and escalation.

Direct agents should not pretend to be multi-reasoning. They can recommend or launch workflows when
the task crosses the value bar for orchestration.

## Still Open

- Keep [optional DorkPipe browser assistance](browser-integration.md) deferred:
  define reusable contribution and authorization APIs before AI page control,
  summaries, annotated requests or explicitly granted history access. Ordinary
  browser settings and extension-based password/autofill remain independent.
- Deliver AI contributions from the existing DorkPipe repository and package pipeline;
  coordinate generic registration and selected-version lifecycle with TASK-039.
- Define the launcher context payload shared with Pipeon-style app launches.
- Decide which YAML contracts exist for MCP connectors and agent/task packs before building rich
  editors.
- Extend the initial `dockpipe.operation_event.v1` JSONL stream into the full DockPipe AI run inspector
  feed, including logs, artifact references, approvals, and task graph state.
- Add a future graph visualizer for repo guidance and task contracts so DockPipe AI can render
  relationships across `AGENTS.md`, `docs/agents/*.yaml`, linked task docs, workflow/package docs,
  and other durable agent-routing sources instead of depending on markdown-link-only tooling.
- Extend the built-in editor where needed; the launcher owns text editing rather than launching the system default editor.
- Design conflict preview and repair flows without turning the app into a full IDE.
- Decide where remote-access YAML lives and how it maps to Cloudflare Tunnel, Let's Encrypt,
  free-domain/subdomain, and bring-your-own-domain flows.
- Define the threat model for exposing the app remotely, including auth, allowed operations,
  approval prompts, audit logs, and teardown.
- Decide the Qt mobile packaging path, authentication model, offline behavior, and which actions are
  safe to expose from mobile.

