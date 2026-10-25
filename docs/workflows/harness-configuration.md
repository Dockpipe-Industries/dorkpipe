# DorkPipe harness configuration

These are DorkPipe package contracts, consumed by its scripts and tooling. They do not turn generic Dockpipe YAML fields into an engine-owned AI scheduler. Install a compatible DorkPipe package before using these settings.

This reference was separated from the Dockpipe workflow YAML reference during the documentation ownership audit. The examples preserve the documented harness behavior; provider login, container builds and orchestration were not requalified by that documentation-only audit. Check the installed package version and its [orchestration contract](../../packages/dorkpipe/resolvers/dorkpipe/assets/docs/orchestration-contract.md).

For generic fields and validation, see the [Dockpipe workflow YAML reference](https://github.com/Dockpipe-Industries/dockpipe/blob/master/docs/workflows/workflow-yaml.md).

## Worker images, authentication and logging

DorkPipe orchestration cloud workers also accept a run-level consumer image override:

```yaml
vars:
  DORKPIPE_ORCH_CONTAINER_IMAGE_PACKAGES: "make cmake libxml2-utils"
```

When Codex or Claude orchestration workers need extra Debian packages, DorkPipe generates a derived
Dockerfile from the provider image, tags the image with a checksum of provider + base image + package
list, builds it once if missing, and runs workers with `--isolate <generated-image>`. This keeps
tooling deterministic and cacheable instead of installing packages inside every worker container at
startup.

This override is intentionally consumer-owned. Resolver images keep only a lean baseline, so
project workflows should request their own heavier language stacks, for example:

```yaml
vars:
  DORKPIPE_ORCH_CONTAINER_IMAGE_PACKAGES: "python3 ruby-full golang-go dotnet-sdk-8.0"
```

The generated Dockerfile adds Microsoft's Debian package feed on demand when the requested package
set includes `.NET` packages such as `dotnet-sdk-8.0`. `DORKPIPE_ORCH_CONTAINER_APT_PACKAGES`
remains accepted as a compatibility alias, but new workflows should use
`DORKPIPE_ORCH_CONTAINER_IMAGE_PACKAGES`.

Cloud Codex/Claude workers run a host-auth preflight before the container starts. API-key env vars
pass immediately; otherwise DorkPipe checks the provider auth files resolved by `dockpipe scope
resolver <name> auth-dir`. When auth is missing and the run is interactive, DorkPipe asks whether to
launch the host login command (`codex login` or `claude auth login`) and re-checks after the user
finishes. Set `DORKPIPE_ORCH_AUTH_LOGIN_ON_MISSING=never` to fail fast, or `always` to launch the
login command without asking. Non-interactive runs fail fast with the manual command to run.

DorkPipe orchestration logging is controlled by `DORKPIPE_ORCH_LOG_MODE`:

- `default` hides raw worker, Docker Compose, and Ollama pull chatter behind progress lines, but
  prints failure log tails.
- `minimal` currently behaves like `default` for orchestration scripts and is reserved for stricter
  future output pruning.
- `verbose` streams raw provider and Docker output.
- `none` suppresses orchestration progress lines where package scripts own the output.

Dev-stack logging can be overridden separately with `DORKPIPE_DEV_STACK_LOG_MODE`; otherwise it
inherits `DORKPIPE_ORCH_LOG_MODE`.

## Scope references, collectors and reusable agents

DorkPipe agent orchestration also accepts full-string scope references in path lists such as
`agent.accessible_paths`, `agent.access.read/write/deny`, and task `context` fields:

```yaml
context:
  required_artifacts:
    - scope:workflow:docs.orchestrate:orchestrate/verify/result.json
    - scope:artifacts:orchestrate/tasks/latest_run_audit/response.md
```

Those references are resolved through the same `dockpipe scope` CLI before prompts and task JSON are
written. Use plain relative paths for normal checkout files.

Shared collectors may declare `starting_points` when a collector needs concrete seeds:

```yaml
shared:
  - path: repo-map.md
    collector: repo_map
    focus: Current orchestration contract
    starting_points:
      - packages/dorkpipe/resolvers/dorkpipe/assets/docs/orchestration-contract.md
```

Use `starting_points` as optional collector hints only. Do not duplicate broad mounted roots there;
mounts and `access.read` define the actual exploration boundary.

For task execution lanes, define reusable role agents in sibling `agents.yml`, then reference those
roles from tasks. If that sibling is absent, DorkPipe searches parent workflow directories for the
nearest `agents.yml`; the sibling always wins. Search stops at the owning `workflows/` directory or,
for package workflows, the package directory containing `package.yml`; it never falls back to an
unbounded repository-level `agents.yml`.

```yaml
agents:
  source_scout:
    role: source scout
    worker: ollama
    worker_type: planning
  patch_decider:
    role: patch decision owner
    worker: codex
    worker_policy:
      mode: require
    work_mode: edit
    worker_type: patch_decision
```

```yaml
tasks:
  - id: scout_repo
    agent: source_scout
    brief: Inventory current repo evidence.
    context:
      required_artifacts:
        - shared/repo-map.md
```

`worker: codex|claude|ollama` belongs on the role definition, not each task. DorkPipe maps the role
to seeded lane defaults such as preferred lane family and model provider. By default
`worker_policy.mode: prefer` lets the orchestrator fall back, compare, or escalate when policy says
it should. Use `worker_policy.mode: require` only when that role must stay on that worker profile.

Role `work_mode` separates readonly artifact collection from direct workspace editing. The default
`artifact` mode tells Codex/Claude workers to inspect mounted sources and return the requested
artifact in `response.md`; DorkPipe apply/promotion writes approved files later. Set `work_mode:
edit` only for implementation or repair tasks, and pair it with writable container mounts plus
matching `agent.access.write` policy.

## Provider-pool model policy

DorkPipe agent workflows can opt selected workflow/subagent workers into the shared provider-pool leasing path without naming a provider-specific YAML field:

```yaml
model_policy:
  execution_mode: provider_pool
  role: reviewer
  session_scope: workflow
  max_active: 1
  queue_timeout_seconds: 30
```

`execution_mode: provider_pool` makes the DorkPipe worker script call `dorkpipe provider-pool prompt --json` for that worker instead of spawning a direct provider CLI. `role` is a provider-neutral attribution/session grouping label. `session_scope: node` isolates each subagent node; `session_scope: workflow` reuses a role session within the workflow run. `max_active` narrows the provider catalog's active lease cap for that policy, and `queue_timeout_seconds` controls how long the worker waits before returning a visible queued failure.

## Agent orchestration

Use `agent:` when a step should declare agent behavior directly in workflow YAML while still letting
shared DorkPipe scripts act as the harness.

Typical uses:

- startup prompt text
- whether to include `AGENTS.md` context
- access policy (`read`, `write`, `deny`) plus lightweight accessible path hints
- model/provider knobs that affect generation
- model policy overrides for attempt, validation, and escalation
- orchestration fanout data such as request, tasks, concurrency, merge, verify, and apply policy
- sibling or bounded-parent `agents.yml` role definitions so worker/model/access policy is reusable
  across workflow families

This keeps user intent in `config.yml` and lets shared scripts materialize the contract instead of
forcing one shell file per workflow shape.

`accessible_paths` is a compatibility/simple-hint field. Prefer `access.read`, `access.write`, and
`access.deny` when the workflow needs a real contract that DorkPipe tooling can materialize into
artifacts and, later, stronger runtime policy.

`agent.orchestration.tasks[].context` entries are required briefing/discovery hints, not a hard
allowlist. Keep them small: request text, compact source maps, seed paths, and previous role outputs.
Let `access.read` and the mounted paths define the broader exploration boundary. Prompts should
explicitly say when a role may inspect additional allowed sources and must cite exact paths for any
claim it carries forward.

Prefer reusable role definitions in a sibling `agents.yml`; when it is absent, DorkPipe uses the
nearest parent `agents.yml` within the workflow or package authoring root. Inline
`agent.orchestration.agents` is available for workflow-local overrides. Tasks reference roles via
`tasks[].agent`. Agent definitions
describe who the worker is: role, worker profile, authority, model policy, access defaults, and
standing constraints. Tasks describe what happens in this workflow: `brief`,
`context.required_artifacts`, `context.seed_paths`, `context.source_roots`, dependencies, and declared
outputs. Keep source boundaries in access policy and mounts, not in task briefing fields.

`agent.orchestration.concurrency` lets DorkPipe-owned harnesses cap worker fanout without hiding
scheduling rules in scripts. `max_workers` caps total runnable workers, while `max_local_workers`
and `max_cloud_workers` cap local and cloud-backed lanes separately.

`agent.orchestration.apply` declares approved artifact-to-worktree writes. DorkPipe harnesses should
write reviewable artifacts first, verify them, require approval when configured, and only then copy
approved content into the checkout as normal uncommitted changes.

`agent.orchestration.tasks[].materialize_outputs` lets one role worker own a coherent output cluster
without becoming one worker per file. The worker returns `<!-- dorkpipe:file path="..." -->` blocks in
its `response.md`; DorkPipe extracts only the declared relative paths into
`tasks/<task-id>/materialized/`.

Apply can then use either:

- explicit `apply.outputs[]` entries with `source` and `path`
- or `apply.target_root` plus `apply.required_artifacts`

When `target_root` is used, DorkPipe infers the full apply set from `tasks/*/materialized/*`,
requires the listed relative artifact paths to exist, and then writes the whole inferred bundle under
the target root. Use this when the workflow needs a minimum required doc set but should still allow
the AI to split or extend the durable file set beyond a rigid static list.
