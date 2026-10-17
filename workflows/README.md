# Repository workflows

Run from the repository root with an explicit installed DockPipe executable:

```sh
dockpipe --workflow-file workflows/check/config.yml
dockpipe --workflow-file workflows/test/config.yml
```

Inspect each configuration before executing it. Host workflows use the local toolchain;
they do not install it or grant network, Git publication, deployment or process-start authority.
Generated output uses `dockpipe scope artifacts`. The root `check` validates guidance and
workflow declarations; it does not qualify unimplemented applications or release delivery.

Hosted CI reads `release/toolchains.lock.json`, which pins the released CLI
version, Linux amd64 archive URL and SHA-256. Bootstrap verifies and extracts the
archive before use. Upgrade the committed lock and qualify these workflows together.
Hosted execution and publication remain unqualified until a successful run.

Use explicit workflow files with the pinned 0.6.11 CLI to avoid its older named-workflow asset lookup issue.
