# DORK-002 — Skills Manager and Target Integration

## Status and Ownership

Deferred vision/backlog, recorded 2026-10-17. Audit before implementation. Shared
DockPipe networking/package foundations, unified MCP and DORK-001 graphs/knowledge/context
remain higher priority. No code, host-skill installation, migration or publication is
requested by this record. DorkPipe owns skill domain operations and contributes a
Skills view inside the existing DockPipe app; core owns generic lifecycle/extension
contracts. No separate application, registry service or mandatory container stack.

## Reuse First

Inspect the current curated skill sources, target-neutral IDs, skills.render workflow,
renderer validation/section overrides and Codex/Claude/generic target adapters before
adding anything. Existing rendering is a reuse point, not proof of a complete skills
manager or safe multi-source lifecycle. Preserve current supported skill IDs and outputs.

## Proposed Scope

- Browse/search/inspect skills with source, provenance, version/digest, compatibility,
  declared requirements and installed/rendered target status.
- Import supported local or versioned package sources; review content and assets before
  activation. Do not invent a second package registry or assume imported content is trusted.
- Select exact project/global/package-scoped skill versions and expose conflicts explicitly.
  Define precedence, dependency ownership and update behavior with generic package pinning;
  never silently replace another project's or the user's own skill files.
- Support reviewable install/render/export/update/disable/remove and rollback through
  authoritative CLI/API operations, with existing-app UI consuming the same status/results.
  Inventory user modifications and preserve them; define ownership before writing host paths.
- Route authorized skill discovery/context access through the unified MCP gateway and reuse
  DORK-001 retrieval/ranking where appropriate. Preserve canonical skill content and separate
  instructions, factual knowledge and runtime policy. Exact tools/resources and host adapter
  contracts need design/protocol review; no conceptual command is claimed to exist.
- Treat imported instructions and bundled assets as untrusted. Skills never approve actions,
  widen filesystem/network access or supersede repository/user rules. Executing bundled
  scripts crosses the normal execution/permission boundary rather than happening on import.
- Record source scope and exclude private content from public renders, exports and caches.
  Keep credentials as references and report missing/unsupported host integrations explicitly.

## Audit and Future Acceptance

1. Inventory existing sources, renderer and actual host integration contracts; document gaps.
2. Prove a versioned skill can be inspected and rendered for supported target fixtures from
   one canonical source, with source/version/scope visible in CLI and app status.
3. Reject conflicting identities, incompatible versions, unsafe paths/links and unexpected
   writes; preserve user edits during upgrade/removal and demonstrate rollback.
4. Prove discovery/context filtering and offline behavior without granting execution authority.
5. Qualify actual supported hosts separately from fixture rendering. No real host skill
   replacement during audit; no new core hardcoded DorkPipe commands or sibling-source builds.

Coordinate the overall audit with DockPipe's
`docs/agents/tasks/agentic-app-ui/direction-review.md` in that repository. This task is
DorkPipe's authoritative skills-manager backlog, not another knowledge initiative.
