# P1 — Move Unified Knowledge & Graph Management to DorkPipe

## Objective

Revisit the existing Unified Knowledge & Context Management backlog initiative and move its ownership from the main DockPipe repository to the **DorkPipe repository**.

DorkPipe has recently been extracted into its own repository. This separation is intentional and should be preserved.

DorkPipe will become the optional intelligence and knowledge-management package for DockPipe, providing:

- Local knowledge bases.
- Markdown and document ingestion.
- RAG and hybrid retrieval.
- Knowledge graphs.
- DAG-based relationship and dependency processing.
- Context indexing and retrieval.
- Existing intelligent context-routing capabilities.
- MCP tools for accessing these capabilities.

These must integrate directly into the existing DockPipe experience.

**Core principle: DockPipe provides the runtime and extensibility. DorkPipe contributes first-class knowledge features. Users should experience one application, not two separate platforms.**

This task is primarily about repository ownership, architectural boundaries, backlog migration, and reuse of existing functionality.

Do not begin a wholesale implementation or rewrite.

## 1. Inspect both repositories

Before making changes, inspect the current DockPipe and DorkPipe repositories.

Determine:

1. How DorkPipe was extracted and how it is currently packaged.
2. Which knowledge, RAG, graph, DAG, and routing systems already exist.
3. How DockPipe installs, registers, loads, updates, and removes packages.
4. How packages currently extend the DockPipe CLI and desktop application.
5. How the unified MCP gateway and package registration architecture are being developed.
6. Which features belong in DockPipe core versus DorkPipe.
7. Which existing backlog tasks cover these features.
8. Which reusable interfaces are required for DorkPipe to extend DockPipe without tight coupling.

Preserve the recent repository extraction.

Do not move DorkPipe's implementation back into DockPipe simply to achieve runtime integration.

## 2. Establish the correct ownership boundaries

### DockPipe core repository

DockPipe owns generic platform infrastructure:

- Core execution runtime.
- Package management and package lifecycle.
- Package capability registration.
- CLI extension interfaces.
- Desktop UI extension interfaces.
- Unified MCP gateway and tool registry.
- Authentication and authorization infrastructure.
- Generic persistence and configuration interfaces where already provided.

These capabilities must remain usable without installing DorkPipe.

### DorkPipe repository

DorkPipe owns AI-specific knowledge functionality:

- Knowledge-source management.
- Local directory and repository indexing.
- Markdown/document processing.
- RAG, embeddings, full-text and hybrid retrieval.
- Knowledge graph construction and querying.
- Structured DAG ingestion and traversal.
- Context selection and routing.
- Knowledge persistence.
- Knowledge-specific CLI commands.
- Knowledge-specific desktop UI features.
- MCP tools exposing knowledge capabilities.

Do not duplicate these implementations inside DockPipe core.

### DockPipe Cloud

Future optional functionality only:

- Cross-machine knowledge synchronization.
- Shared team knowledge.
- Hosted knowledge repositories.
- Hosted retrieval and graph services.
- Centralized collaboration and access policies.

Do not implement Cloud functionality in this initiative.

## 3. DorkPipe as a first-class feature package

DorkPipe must remain independently installable and versioned through the existing DockPipe package system.

Once installed, its capabilities should become first-class features of the running DockPipe application.

Expected user experience:

```text
Install DockPipe
      |
      v
Install DorkPipe package
      |
      +-- Knowledge features appear in DockPipe CLI
      |
      +-- Knowledge management appears in DockPipe UI
      |
      +-- Graph/DAG tools become available
      |
      +-- Knowledge tools register with unified MCP
      |
      +-- Existing DockPipe runtime handles lifecycle
```

Do not require users to operate a second application.

Do not launch a separate MCP server for DorkPipe.

Do not require a Docker container, separate daemon, or dedicated database service for ordinary local knowledge operations unless existing technical constraints genuinely require one.

Prefer integration with the existing DockPipe process and runtime for trusted first-party functionality.

Preserve appropriate security and fault isolation where needed.

## 4. Top-level CLI integration

DorkPipe must extend the existing DockPipe CLI using established command-registration conventions.

Knowledge functionality should appear as top-level DockPipe features rather than requiring users to invoke a separate DorkPipe CLI.

Illustrative command structure:

```bash
dockpipe knowledge add ./docs
dockpipe knowledge list
dockpipe knowledge index
dockpipe knowledge search "deployment architecture"
dockpipe knowledge status

dockpipe graph import ./architecture.json
dockpipe graph query "service dependencies"
dockpipe graph list
```

These are conceptual examples.

Inspect existing CLI conventions before selecting the final syntax.

Requirements:

- Register commands only when DorkPipe is installed and enabled.
- Use the existing DockPipe command-dispatch and configuration mechanisms.
- Support headless execution.
- Support scripting and machine-readable output where appropriate.
- Preserve existing CLI behavior.
- Uninstalling or disabling DorkPipe removes its command contributions cleanly.
- Avoid modifying CLI core code for every additional DorkPipe command.

If the current package system cannot register CLI capabilities, identify the smallest generic extension required in DockPipe core.

## 5. First-class desktop UI integration

Installing DorkPipe should enable native-feeling knowledge-management features within the existing DockPipe desktop application.

Potential top-level features:

**Knowledge**
- Add local directories or repositories.
- Manage knowledge sources.
- Configure indexing.
- View indexing progress and health.
- Search and inspect indexed content.
- Manage local knowledge collections.

**Graphs**
- Import structured graph or DAG data.
- Inspect relationships and dependencies.
- Explore nodes and edges.
- Query graph relationships.
- View indexing and extraction status.

**Context**
- Manage existing context-routing capabilities.
- Inspect available context sources.
- Configure retrieval behavior.
- Expose context to authorized AI clients.

Requirements:

- Follow existing DockPipe UI architecture and visual conventions.
- Reuse existing navigation, canvas, panels, state management, and components.
- Use the same underlying core services as the CLI.
- Avoid duplicating business logic in the frontend.
- Do not create a standalone DorkPipe UI application.
- Dynamically register or reveal these features when DorkPipe is installed.
- Remove or disable contributed UI features when the package is disabled.

If necessary, introduce a generic first-party UI contribution interface into DockPipe core.

Do not introduce arbitrary unrestricted UI plugin execution without evaluating security and compatibility implications.

## 6. Unified MCP integration

DockPipe core owns the unified MCP server.

DorkPipe contributes knowledge-related tools through the existing unified MCP tool registry.

Example capabilities:

```text
dorkpipe.knowledge.search
dorkpipe.knowledge.index
dorkpipe.knowledge.sources
dorkpipe.context.retrieve
dorkpipe.graph.query
dorkpipe.graph.traverse
dorkpipe.graph.import
```

These are illustrative tool identities.

Use the established MCP naming and namespacing conventions.

Requirements:

- One DockPipe MCP endpoint.
- No separate DorkPipe MCP process.
- Package-scoped tool registration.
- Authorization-aware tool discovery.
- Explicit read/write permissions.
- No collisions with other MCP packages.
- Stable tool identifiers.
- Shared knowledge implementations between MCP, CLI, and UI.
- Tools automatically register when DorkPipe is enabled.
- Tools unregister when DorkPipe is disabled.

Knowledge indexing or graph mutation must remain subject to appropriate filesystem and execution permissions.

## 7. Local knowledge sources

The initial functionality must be local-first.

Users should be able to point DorkPipe at:

- Local directories.
- Markdown documentation repositories.
- Source repositories.
- Structured JSON/YAML data.
- Existing graph/DAG datasets.
- Other already-supported document sources.

DorkPipe should reuse its existing ingestion and indexing capabilities.

Requirements:

- Source registration and removal.
- Incremental indexing where supported.
- Persistent local indexes.
- File-change detection where practical.
- Configurable inclusion and exclusion rules.
- Search and retrieval.
- Index rebuild and repair.
- Clear source provenance.
- Workspace or project scoping.

Avoid assuming that every source requires embeddings.

Support appropriate combinations of full-text search, semantic retrieval, and structured graph queries using existing implementations.

## 8. Graph and DAG capabilities

Reuse the existing graph and DAG infrastructure rather than creating a new graph database or processing engine.

Preserve the conceptual distinction:

- **Knowledge graph:** Represents entities and relationships, potentially including cycles.
- **DAG:** Represents directed acyclic relationships such as dependency or execution ordering.

Support ingestion of explicit structured relationships.

Allow automatic relationship extraction where existing capabilities support it.

Do not make AI-based graph generation mandatory.

Users should be able to provide graph data directly without involving an LLM.

Expose graph capabilities consistently through CLI, UI, and MCP.

Do not force graph data into a DAG representation when cyclic relationships are valid.

## 9. Repurpose existing context-routing infrastructure

Inspect DorkPipe's existing intelligent routing and context-selection systems.

The previous architecture may contain functionality originally intended for more complex AI orchestration.

Determine which components can be repurposed for:

- Knowledge source selection.
- Relevant context retrieval.
- Graph-assisted retrieval.
- Cross-document relationships.
- Context ranking.
- Repository awareness.
- Efficient knowledge delivery to agents.

Avoid carrying forward unnecessary routing complexity.

Do not make DorkPipe responsible for controlling an AI client's entire workflow.

The AI client remains responsible for its reasoning and workflow.

DorkPipe supplies authorized knowledge and context.

Retain genuinely useful routing capabilities as internal services when appropriate.

## 10. Runtime and resource constraints

This feature should remain lightweight.

Normal local usage should not require:

- Separate containers.
- Another MCP server.
- A separately managed database service.
- A second persistent daemon.
- Cloud infrastructure.
- A new orchestration system.

Reuse existing local persistence and indexing mechanisms where practical.

Evaluate memory usage, idle resource consumption, indexing concurrency, startup performance, and shutdown behavior.

Expensive indexing or inference operations may use background work or isolated execution where technically justified.

Do not compromise application stability merely to force everything into one process.

The normal user experience must remain a single integrated DockPipe installation.

## 11. Package installation and lifecycle

Use the existing DockPipe package registry and release mechanisms.

DorkPipe must support:

- Installation.
- Version compatibility checks.
- Updates.
- Enable/disable.
- Configuration.
- Uninstallation.
- Capability registration.
- CLI command registration.
- Desktop UI contributions.
- MCP tool registration.
- Migration of existing knowledge data.
- Cleanup of runtime resources.

Uninstalling the package must not silently delete user knowledge sources, indexes, or graph data.

Follow existing DockPipe data-retention conventions.

Ensure package upgrades can safely migrate existing metadata and indexes.

## 12. Backlog migration

**Move the existing Unified Knowledge & Context Management initiative from the DockPipe repository backlog to the DorkPipe repository backlog.**

This is a migration of ownership, not a duplicate initiative.

Required actions:

1. Locate the existing initiative and all related backlog tasks.
2. Read their requirements, acceptance criteria, dependencies, and relevant discussion.
3. Identify any duplicate or overlapping DorkPipe tasks.
4. Reconcile duplicate work before creating new tasks.
5. Create or update the corresponding initiative in the DorkPipe repository.
6. Preserve the original functional requirements that remain relevant.
7. Update architecture assumptions to reflect DorkPipe's new ownership.
8. Preserve links to the originating backlog items.
9. Update cross-repository dependencies.
10. Mark superseded DockPipe backlog items as moved or superseded using established repository conventions.
11. Avoid deleting historical discussion or useful implementation context.
12. Confirm that the final DorkPipe backlog accurately represents the intended work.

If a backlog item describes a generic DockPipe capability, retain ownership in the DockPipe repository.

Examples include generic CLI extension mechanisms, UI contribution interfaces, and unified MCP gateway infrastructure.

Create cross-repository dependencies where DorkPipe requires those capabilities.

Do not migrate unrelated DockPipe core work.

Do not alter Task 38's Terraform-specific ownership or scope as part of this migration.

## 13. Recommended backlog breakdown

Organize the DorkPipe initiative around these work areas, adjusting to what already exists.

### DorkPipe integration foundation

- Package lifecycle integration.
- CLI contributions.
- Desktop UI contributions.
- Unified MCP tool registration.
- Shared configuration and service interfaces.

### Local knowledge management

- Knowledge-source registration.
- Directory and repository ingestion.
- Markdown processing.
- Existing RAG and hybrid search.
- Index persistence and lifecycle.

### Graph/DAG management

- Structured graph ingestion.
- DAG ingestion.
- Relationship querying.
- Graph traversal.
- UI visualization.
- MCP exposure.

### Context services

- Refactor existing router.
- Knowledge retrieval.
- Context selection.
- Graph-assisted retrieval.
- Existing repository awareness.

### Quality and integration

- Resource usage.
- Migration compatibility.
- Error handling.
- CLI/UI/MCP parity.
- Package installation and removal tests.
- Offline operation.

### Future dependency — DockPipe Cloud

Document potential hosted synchronization and collaboration integration points.

Do not implement them now.

## 14. Acceptance criteria

A user installs DockPipe without DorkPipe.

DockPipe continues to function normally, including its core CLI, runtime, package manager, and unified MCP gateway.

The user installs DorkPipe from the existing package registry.

Knowledge, graph, and context features appear in the DockPipe CLI and desktop UI.

The user registers a local Markdown directory.

DorkPipe indexes it and makes its content searchable.

The user imports structured graph/DAG data.

DorkPipe exposes graph query and traversal capabilities.

An MCP-compatible AI client connects to DockPipe's existing unified MCP endpoint and discovers the authorized DorkPipe tools.

The AI can retrieve relevant knowledge without requiring a separate DorkPipe server.

The same knowledge data and underlying functionality are used by the CLI, desktop UI, and MCP tools.

The system operates locally without DockPipe Cloud.

Disabling DorkPipe removes its contributed commands, UI entries, and MCP tools without breaking DockPipe core.

Re-enabling DorkPipe restores access to existing knowledge data.

The main DockPipe repository contains only the generic extension infrastructure it needs.

The DorkPipe repository owns the knowledge implementation and its backlog.

No redundant containers or standalone services are introduced for normal local operation.

## 15. Execution instructions

This request is for architectural refinement and backlog migration.

Proceed in this order:

1. Inspect DockPipe and DorkPipe.
2. Inventory existing implementations.
3. Identify reusable components and missing generic extension points.
4. Establish repository ownership boundaries.
5. Revise the existing knowledge initiative.
6. Migrate appropriate backlog tasks to DorkPipe.
7. Update cross-repository dependencies and documentation.
8. Report the migration and proposed implementation sequence.

Do not begin a large feature rewrite.

Do not undo the DorkPipe repository extraction.

Do not create duplicate backlog items.

Do not introduce a separate MCP implementation.

Prefer existing DockPipe architectural conventions wherever possible.

**Final target: DockPipe remains a lightweight extensible runtime. DorkPipe is an optional, independently developed package that adds first-class knowledge, RAG, graph, DAG, and context capabilities through DockPipe's existing CLI, desktop UI, and unified MCP gateway.**