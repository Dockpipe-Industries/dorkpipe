# DORK-001 — Unified Knowledge, Graph and Context Management

## Status and Source of Truth

**P1**, new feature backlog, added 2026-10-17. DorkPipe owns this initiative and its implementation.
The user clarified that this is a **new feature**, superseding the attached request's assumption of
an existing initiative to migrate. No predecessor was found or needs to be marked moved/closed.
The [full request](design-request.md) preserves the original wording; this clarification governs
its migration sections. No feature implementation, publication or extraction reversal is authorized.

DorkPipe is an optional, independently versioned package that adds knowledge, RAG, graph/DAG and
context features to the existing DockPipe application. DockPipe remains usable without it.
[Inventory and integration dependencies](integration-inventory.md) record current evidence and gaps.
Do not copy implementation into DockPipe core or reintroduce sibling-source build dependencies.

## Agent Bootstrap and MCP-Routed Knowledge — Review Required

User direction, 2026-10-17: AGENTS.md becomes a minimal versioned bootstrap for
project identity, essential rules, the configured DockPipe MCP reference and safe
offline instructions. The unified DockPipe gateway routes authenticated context
requests to this package; DorkPipe owns scoped retrieval, ranking, durable decisions,
task state, provenance, source revisions, freshness and supersession.

Retrieved content is evidence, not authority to override local repository rules,
modify permissions or approve execution. Enforce source access before search,
snippets and graph traversal; isolate private/public results, caches and exports.
Surface conflicting or superseded decisions rather than silently merging them.
Knowledge writes and promotion need authorized ownership; generated assertions must
not silently become accepted decisions. An index must remain rebuildable from
identified authoritative records. Provide bounded/cancellable retrieval and exports.

Markdown remains an input/export format and versioned specs remain useful. Inventory
current guidance, source ownership, migration, backups, rollback and host MCP setup
before replacing file routing or reducing working AGENTS files. On MCP failure,
retain minimal local guidance, report missing context and stop operations requiring
unavailable policy. Never infer permission from missing knowledge.

Latest user priority: shared DockPipe core networking and package/version foundations,
then unified MCP, then DorkPipe graphs, knowledge/search and context. Chat, model UI
and richer AI authoring remain deferred and do not gate these releases. DorkPipe may
contribute a Models area with user-selected supported local/remote/hosted targets;
neither inference nor a separate local service stack gates basic knowledge features.
Pipeon retirement and editor consolidation are tentative; preserve current identities,
settings, sessions, packages and consumers until migration is reviewed.

Audit the whole direction with the user before any implementation or retirement.
DockPipe's coordination review is docs/agents/tasks/agentic-app-ui/direction-review.md
in that repository; this record remains the authoritative knowledge feature backlog.
No repository rename, publication or runtime work is authorized by this update.

## Authorized Repository Split — 2026-10-17

The user supersedes the earlier deferral: rename current private `dorkpipe` to
`dorkpipe-platform` for website/platform and private integration-specific code, and
create new public `dorkpipe` for reusable package, MCP, editor and AI/knowledge code.
DORK-001 and DORK-002 move with their feature implementation ownership.

Preserve private history, immutable artifacts and attribution. Review source contents,
SDK distribution, publisher policy, build inputs, release environments and pinned
consumers before retargeting. Do not expose private integrations or copy secrets into
the public snapshot. The repository rename and creation are complete; source/bootstrap and hosted qualification
are tracked separately. This record does not claim a feature implementation.
Finish the direction audit and related staging checkpoint before new feature work.

## Ownership

| Owner | Scope |
| --- | --- |
| DockPipe | Generic runtime, package lifecycle/registration, CLI/UI contribution contracts, unified MCP gateway, authorization and existing generic configuration/persistence interfaces |
| DorkPipe | Sources, document processing, local indexes, embeddings/full-text/hybrid retrieval, knowledge graphs, DAG ingestion/traversal, context ranking/routing, domain persistence, commands, views and MCP contributions |
| DockPipe Cloud | Future optional synchronization, teams, hosting, retrieval and collaboration policies; no implementation in this initiative |

Core runtime and CLI/API contracts remain authoritative. Knowledge business logic and data live in
DorkPipe and are shared by CLI, UI and MCP; the frontend never implements a second knowledge service.
The AI client owns its reasoning/workflow. DorkPipe supplies authorized knowledge and context rather
than taking control of the client's entire workflow.

## Integration Foundation

- Keep existing package identity, independent releases and verified artifact/SDK consumption.
  Install/update/enable/disable/configure/uninstall through DockPipe's existing package system.
- Contribute top-level DockPipe CLI features when installed/enabled, using generic command dispatch
  and configuration. `dockpipe knowledge ...` and `dockpipe graph ...` are conceptual syntax to
  validate, not existing commands. Support headless use, scripting and structured output. Do not
  require a separate DorkPipe CLI or add a core command branch for each domain operation.
- Contribute native-feeling Knowledge, Graphs and Context views inside the existing desktop. Reuse
  navigation, canvas, panels, state management and components. Views manage sources/indexing,
  progress/health, search/content inspection, collections, graph nodes/edges and context selection.
  Do not build a standalone UI or enable unrestricted UI plugin execution without boundary review.
- Register package-scoped tools through the single DockPipe MCP gateway. Use reviewed stable
  namespaced identities, collision rejection, authorization-aware discovery and explicit read/write
  policy. Tool examples in the request are illustrative. No separate DorkPipe MCP process is
  required for these features; existing clients must have a compatible transition plan.
- Enable/disable must register/unregister command, view and tool contributions consistently. Apply
  filesystem, source-scope and execution permissions at the owning boundary for indexing/mutation.
- Use one authoritative configuration and domain data model; changes from CLI, UI and MCP must be
  visible through the other surfaces with consistent validation and errors.

## Local Knowledge Management

Support local directories, Markdown/document repositories, source repositories, JSON/YAML,
explicit graph/DAG datasets and already-supported sources after verifying their capabilities.

Deliver source add/list/remove, inclusion/exclusion rules, provenance and workspace/project scoping;
incremental indexing and file-change detection where supported; persistent indexes, progress/health,
search/retrieval, rebuild and repair. Evaluate existing ingestion first. Full-text, semantic and
structured retrieval are complementary; embeddings and AI inference are not mandatory for every
source. Do not claim the existing PostgreSQL query worker is a complete ingestion/RAG service.

## Graph and DAG Management

Reuse evidence relationships and graph/DAG infrastructure where its contracts fit. Knowledge graphs
may contain cycles; dependency/execution DAGs must be acyclic. Do not conflate them or force cyclic
knowledge into an execution DAG. Accept structured graph/DAG input without an LLM. Provide query,
traversal, import/list, extraction/index status and UI relationship exploration through the same
underlying services. Automatic extraction is optional where verified existing functionality permits.
Avoid a new graph database/engine unless a documented gap proves it necessary.

## Context Services

Inspect and reuse relevant parts of the current request router, repository evidence extraction,
source selection, ranking and context construction. Separate these services from model execution,
workflow control and orchestration complexity. Include graph-assisted retrieval and cross-document
relationships without inventing a new orchestrator or making AI-generated graphs a prerequisite.

## Persistence, Resource and Lifecycle Requirements

Ordinary local operations should need no Cloud, extra MCP server, container, second persistent daemon
or separately managed database. Prefer existing local persistence and runtime execution for trusted
first-party functionality; preserve security and fault isolation. Document genuine technical
constraints before introducing a service dependency. Existing stack/pgvector paths are optional reuse
candidates, not required deployment architecture for this feature.

Measure memory, idle cost, indexing concurrency, startup and shutdown. Bound and cancel expensive
work; isolate indexing/inference where needed for application stability. Define safe cleanup of
workers/watchers on disablement and uninstall. Uninstall must not silently delete user sources,
indexes or graph data. Preserve existing data-retention conventions and prove upgrade/migration,
recovery and re-enable behavior with fixtures before touching real user data.

## Delivery Sequence and Acceptance

| Work area | Acceptance gate |
| --- | --- |
| Integration foundation | Identify smallest missing generic CLI/UI contribution seams with DockPipe owners; prove optional install/enable/disable across CLI, desktop and unified MCP using versioned package contracts |
| Local knowledge | Register a local Markdown directory, index/search it with provenance, exclusions and scope isolation; prove persistence, update/rebuild/repair and offline operation |
| Graph/DAG | Import explicit cyclic graph and acyclic DAG fixtures without an LLM; query/traverse consistently; reject invalid DAG cycles without discarding valid graph relationships |
| Context | Retrieve/rank authorized source and relationship evidence through existing components, without requiring orchestration of the consuming AI client |
| Quality/integration | Demonstrate CLI/UI/MCP parity, cancellation/failure reporting, bounded resources, install/update compatibility and migration/retention fixtures |

Full user scenario: DockPipe works without DorkPipe; installing/enabling DorkPipe reveals Knowledge,
Graphs and Context contributions. Local Markdown becomes searchable, structured graph/DAG data is
queryable, and an authorized client uses the existing MCP endpoint. CLI/UI/MCP share data and behavior.
No Cloud or redundant local services are required. Disable removes contributed commands, views and
tools without breaking core; re-enable restores existing data. Uninstall retains user data under the
established retention policy. Unsupported/unauthorized sources and mutations fail safely.

## Scope and Coordination

This record is the single knowledge initiative. DockPipe retains only generic extension requirements
in TASK-039, coordinating existing TASK-020 catalog/UI contracts where relevant. TASK-038 Terraform
ownership and scope are unchanged. TASK-040 imports and TASK-042 federation remain generic peers,
not new DorkPipe-specific implementations. DockPipe AI's separate application backlog, spatial
Cockpit work and DorkPipe's existing orchestrator backlog are not absorbed or rewritten here.

Future Cloud synchronization/collaboration may consume stable source IDs, versioned records and
access contracts, but it is deferred. Complete design/reuse decisions before implementing this feature.
