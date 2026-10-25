# DorkPipe agent guide

DorkPipe owns the agentic package/harness, separate MCP package and companion editor integration. It consumes generic Dockpipe primitives. AI features, including knowledge/context, chat and model integrations, belong to DorkPipe and contribute to the existing DockPipe app, CLI and unified MCP gateway. They do not define a separate DockPipe AI app/package; this integration remains backlog work pending direction review.

Read `packages/dorkpipe/README.md`, `README-dorkpipe-workflows.md` beside it and affected package manifests/helpers/tests for orchestration; `packages/dorkpipe-mcp/README.md` for MCP; `tooling/vscode-extensions/README.md` and `.github/workflows/editor-candidates.yml` for editor work. Extraction evidence is in `README.md`, `MIGRATION-SOURCES.json` and `EDITOR-MIGRATION-SOURCES.json`.

Preserve `dorkpipe`/`dorkpipe.mcp` identities and relative layouts. Package logic stays in package YAML/assets/scripts/helpers. Pipeon consumes versioned VSIX artifacts with integrity checks; do not duplicate editor implementations. Preserve provider-neutral contracts, approval evidence and runtime-owned session lifecycle. Workflows must improve quality, safety, cost, review effort or rerun value over one strong direct worker.

A pinned Go compatibility SDK builds/tests the helpers independently; verified source hooks consume prepared artifacts; the earlier private package feed was qualified; this public source transition requires new hosted qualification. Read `WORKFLOWS.md` and `tooling/go_candidate.py` for the candidate contract. Do not conceal dependencies behind sibling paths or retire originals from compilation alone. Preserve inherited Apache-2.0 and provenance; private visibility does not alter inherited rights.

## Working rules

- Default: `gpt-6.1-sol`, Medium reasoning. Use bounded subagents for useful independent work with explicit ownership/checks; avoid overlapping edits or expensive fanout. Escalate difficult seams only when a stronger model likely lowers total cost or rework.
- Inspect instructions and read-only Git state first. Preserve staged, unstaged, untracked and unrelated work. Git lifecycle uses runtime session actions; no raw Git mutations. Commit, push, publication, hosted dispatch and live startup require user authorization.
- Initialize the root with `dockpipe init`, preserving existing files. Run `dockpipe --workflow-file workflows/check/config.yml`; use declared root `build`/`test` workflows for builds/tests. Inspect their `workflows/<name>/config.yml`. Workflow = what, runtime = where, resolver = tool/profile, strategy = lifecycle. Keep scripts/assets workflow-owned; reuse existing helpers. Validate changed YAML with `dockpipe workflow validate <path>`.
- Follow local architecture and readable code conventions. Preserve ABI, errors/cancellation and performance contracts. Keep generated outputs ignored and credentials as references. Verify sandbox capabilities; never bypass restrictions.
- Report changed areas, checks, skips, artifacts and limits. Distinguish scaffold/local/offscreen, installed-SDK/native-interactive and hosted/release proof. Update canonical docs without duplicate guidance.

The pinned DockPipe bootstrap uses explicit root workflow files: `dockpipe --workflow-file workflows/check/config.yml` and the corresponding file for other root workflows. This avoids the older named-workflow asset lookup issue; preserve package-local workflow assets. Qualify named execution when upgrading the CLI lock.

Controlled consumers pin released dependency versions and artifact checksums; GitHub Actions use verified full commit SHAs. Upgrade the committed pin and qualify affected consumers together. Do not silently select latest, a branch tip or sibling source in release builds.

## Feature backlog ownership

Read [docs/agents/task-index.yaml](docs/agents/task-index.yaml) for DorkPipe-owned feature work.
DORK-001 owns the new optional knowledge/graph/context initiative; DockPipe owns generic CLI/UI/MCP
extension contracts. Preserve the extraction and current package compatibility. The target single
gateway integration is backlog work, not a claim that the existing separate MCP package is retired.

Repository ownership: this public repository owns reusable DorkPipe packages, MCP,
editor integrations and the DORK-001/DORK-002 feature backlog. The original repository
was renamed to private `dorkpipe-platform`; its history and frozen releases remain there.
Website/platform and private integrations stay separate. See REPOSITORY-MIGRATION.json
for provenance. The public Go SDK is pinned independently; native SDKs are excluded.
Finish the direction audit and qualified staging checkpoint before new feature work.

Agent guidance routes through [docs/agents/index.yaml](docs/agents/index.yaml).
Dockpipe and PipeLang own their language extensions; historical extraction records
do not restore those implementations here.
