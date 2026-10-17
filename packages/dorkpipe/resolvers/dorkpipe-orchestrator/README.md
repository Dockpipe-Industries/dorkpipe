# dorkpipe-orchestrator

**DorkPipe** — DAG orchestration on top of Dockpipe. This resolver declares the
workflow; the shared `dorkpipe` resolver owns its host script, example spec and binary.

- **Spec:** the shared resolver's `packages/dorkpipe/resolvers/dorkpipe/assets/spec.example.yaml`
  (nodes: shell → Ollama → optional Codex escalation).
- **Compose:** `packages/dorkpipe/resolvers/dorkpipe/assets/compose/docker-compose.yml` for Postgres+pgvector and Ollama.
- **Run directly:** `packages/dorkpipe/bin/dorkpipe run -f packages/dorkpipe/resolvers/dorkpipe/assets/spec.example.yaml --workdir .`
- **Run via Dockpipe workflow:** `dockpipe --workflow dorkpipe-orchestrator --workdir . --`.
  The logical `scripts/dorkpipe/run-orchestrator.sh` path resolves to the installed
  shared `dorkpipe` resolver, whose script invokes its packaged binary.

Principles: deterministic prep, local-first, parallel levels, pgvector when you add those nodes, Codex on escalation (or explicit non-escalate codex nodes). See **`lib/README.md`** (Go module).

**Self-analysis (repo → Cursor handoff):** use the packaged workflows **`dorkpipe-self-analysis`** or **`dorkpipe-self-analysis-host`**. Optional local sidecar: **`packages/dorkpipe/resolvers/dorkpipe/assets/scripts/dev-stack.sh`**. Writes package-scoped handoff artifacts such as **`dockpipe scope --package dorkpipe handoff/orchestrator-cursor-prompt.md`** and **`dockpipe scope --package dorkpipe handoff/paste-this-prompt.txt`**.
## Authoring note

The shared resolver's host scripts use the core SDK:

- **Shell:** use **`dockpipe get ...`** for plain context reads; bootstrap **`eval "$(dockpipe sdk)"`** only for shell-specific actions like **`dockpipe_sdk init-script`**
- **DorkPipe package CLI:** use the package-local helper under
  **`packages/dorkpipe/resolvers/dorkpipe/assets/scripts/lib/dorkpipe-cli.sh`**
  when a script in this package needs to invoke the DorkPipe tool itself.
