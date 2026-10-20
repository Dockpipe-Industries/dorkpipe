Use the DorkPipe orchestration contract instead of a single-worker flow.

Follow this sequence:

1. Read `scope:resolver:dorkpipe:assets/docs/orchestration-contract.md`.
2. Inspect `packages/dorkpipe/workflows/docs.orchestrate/`.
3. Treat the work as:
   - plan
   - task graph
   - worker task artifacts
   - merge
   - verify
   - approve
4. Keep `codex`, `claude`, and `ollama` as worker specializations beneath the same contract.
5. Prefer editing `steps[].agent` in `config.yml` before creating any new workflow shell glue.
6. Only change `scope:resolver:dorkpipe:assets/scripts/orchestrate-*.sh` when the generic primitive itself needs to grow.

Primary files:

- `packages/dorkpipe/workflows/docs.orchestrate/config.yml`
- `packages/dorkpipe/workflows/docs.orchestrate/README.md`
- `scope:resolver:dorkpipe:assets/scripts/orchestrate-plan.sh`
- `scope:resolver:dorkpipe:assets/scripts/orchestrate-run-task.sh`
- `scope:resolver:dorkpipe:assets/scripts/orchestrate-merge-results.sh`
- `scope:resolver:dorkpipe:assets/scripts/orchestrate-verify-results.sh`
- `scope:resolver:dorkpipe:assets/scripts/orchestrate-approve.sh`
