# DorkPipe

DorkPipe is an optional, independently versioned DockPipe package for governed AI
workflows and agent tooling. Its package sources, MCP compatibility bridge and editor
integrations are maintained here. DockPipe core remains usable independently.

## Build and validation

Use the pinned DockPipe compiler and generic Go compatibility SDK in `release/`.
[WORKFLOWS.md](WORKFLOWS.md) describes root DockPipe workflows for checks, builds,
package candidates and editor tests. SDK downloads do not require private repository
access. Credentials for hosted package uploads stay in protected release environments.

This repository transition targets DorkPipe 0.6.5. Earlier 0.6.4 staging artifacts
remain immutable; public source migration requires its own hosted qualification and
new staging artifacts. Source visibility and package distribution are separate choices.

## Feature direction

The [backlog](docs/agents/task-index.yaml) records proposed features, not shipped behavior.
DORK-001 owns knowledge, graph/DAG and context contributions to DockPipe's CLI,
existing desktop and unified MCP. DORK-002 is the deferred skills manager.
Shared DockPipe networking/package foundations and unified MCP precede these features;
chat and model-management UI remain deferred. Ordinary local features must not require
a separate AI application or mandatory container/database stack.

## Provenance

This is an audited source snapshot from the original repository, now private
`Dockpipe-Industries/dorkpipe-platform`. Private history and historical releases were
preserved there. Website/platform and private integrations belong there; reusable
package code belongs here. See [REPOSITORY-MIGRATION.json](REPOSITORY-MIGRATION.json),
[LICENSE](LICENSE), MIGRATION-SOURCES.json and EDITOR-MIGRATION-SOURCES.json for
inherited licensing and source attribution. Private ForgePipe/Nucleon SDKs are excluded.
