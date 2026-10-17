# DORK-001 — Existing Components and Cross-Repository Dependencies

Inspected on 2026-10-17 in the extracted DorkPipe checkout and current DockPipe checkout. This is
source/documentation evidence, not a feature, performance or provider qualification result.

## Existing DorkPipe Components

| Evidence | Reuse candidate and limits |
| --- | --- |
| `README.md`, `MIGRATION-SOURCES.json`, `EDITOR-MIGRATION-SOURCES.json`, `WORKFLOWS.md` | Extracted repository with preserved provenance, independent workflows and pinned compatibility SDK; preserve this boundary |
| `packages/dorkpipe/package.yml` | Existing `dorkpipe` umbrella package, version 0.6.4 at inspection; extend package-owned functionality and retain controlled updates |
| `packages/dorkpipe/lib/cmd/dorkpipe/request.go` | `chooseRoute`, `buildWorkspaceChatContext`, source/snippet selection and evidence graph construction; extract/reuse useful knowledge operations without carrying client workflow control into the feature |
| `packages/dorkpipe/lib/reasoning/artifact.go`, `evidence.go` | Retrieval/evidence records, node/edge data and language-aware extraction; candidate basis for provenance/ranking, not proof of a persistent general knowledge graph |
| `packages/dorkpipe/lib/spec/spec.go`, `scheduler/`, `engine/` | Existing execution DAG models, dependencies and scheduling; assess reusable traversal/validation separately from general cyclic knowledge relationships |
| `packages/dorkpipe/lib/workers/workers.go` | `runPGVector` opens PostgreSQL and executes supplied SQL; proves a query integration, not embedded indexes, Markdown ingestion, embedding generation or complete hybrid retrieval |
| `packages/dorkpipe/lib/statepaths/`, `userinsight/` | Package-owned paths and local structured knowledge candidates; inspect ownership, schema and migration before choosing index storage |
| `packages/dorkpipe/README.md`, `packages/dorkpipe-mcp/` | Current separate MCP/compose/PostgreSQL control plane; existing behavior must be preserved during compatible integration, but is not the target requirement for ordinary local knowledge use |

A complete ingestion/embedding/hybrid-search implementation was not established by this bounded
inspection. The request's reuse direction is mandatory, but missing capabilities must be recorded
honestly rather than represented as already shipped. No broad replacement is approved.

## DockPipe Dependencies

Repository: `Dockpipe-Industries/dockpipe`. Paths below identify source/backlog contracts in that
repository, not sibling filesystem imports. Current unpublished backlog changes must be coordinated
before creating durable release/version dependencies.

| Contract/record | Dependency and ownership |
| --- | --- |
| `docs/agents/tasks/unified-mcp-gateway/index.yaml` (TASK-039) | Generic lifecycle, capability/tool registration, namespacing, profiles, shared auth and authoritative CLI/API management |
| `docs/agents/tasks/unified-mcp-gateway/dorkpipe-knowledge-boundary.md` | Reverse ownership pointer and generic CLI/UI contribution gaps; no duplicate knowledge initiative |
| `docs/agents/tasks/unified-mcp-gateway/cli-first-management.md` | CLI-first, headless, shared configuration and UI parity requirements apply to these contributions |
| `docs/agents/tasks/declarative-application-surfaces-and-target-builders/index.yaml` (TASK-020) | Existing normalized application/catalog ownership; coordinate contribution needs without requiring wholesale UI/PipeLang replacement |
| `src/lib/application/catalog_cmd.go`, `package_cmd.go` | Existing catalog and package command surfaces; verify dynamic top-level command registration and lifecycle support before selecting new syntax |
| `src/app/tooling/dockpipe-launcher/src/WorkflowCatalog.cpp`, `PackageCommand.cpp`, `PackageManagerDialog.cpp` | Existing normalized CLI result consumption and package UI; reusable frontend patterns, not proven dynamic domain UI registration |

## Smallest Gaps to Resolve

1. Determine whether existing installed package metadata can register top-level commands. If not,
   extend a generic contribution/dispatch contract in DockPipe; DorkPipe supplies domain operations.
2. Determine how trusted first-party packages contribute navigation/panels and lifecycle state through
   existing UI/catalog contracts. Review compatibility, permissions and fault isolation before any
   code-loading mechanism. No arbitrary unrestricted UI execution.
3. Reuse TASK-039 for package tools on one gateway; plan compatibility for the extracted legacy MCP
   package without pulling DorkPipe source back into core or requiring its separate process.
4. Choose local index/graph persistence after reviewing reusable code and offline resource costs;
   define source ownership, data retention and migrations before selecting a new backend.
5. Define shared domain interfaces consumed by CLI/UI/MCP. Capture structured errors, cancellation,
   permission checks and status/progress once, not as separate frontend implementations.

No existing knowledge initiative or duplicate was found in either local backlog. The user's explicit
clarification identifies this as new work, so no history was deleted and no predecessor is marked
moved. Origin is the attached design request plus that clarification; future discovered related
records should be linked/reconciled here rather than spawning a second initiative.
