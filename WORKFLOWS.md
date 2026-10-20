# Root DockPipe workflows

Use an installed, explicitly selected DockPipe binary from this repository root.
`dockpipe --workflow-file workflows/check/config.yml` validates the workflow declarations and SDK importer rejection
cases. `editor.candidate` installs locked npm dependencies, tests and creates versioned
VSIX candidates; it requires network access and the declared Node toolchain.

For local Go builds, select immutable local SDK inputs:

```sh
export DOCKPIPE_GO_SDK_MANIFEST=/absolute/path/sdk.json
export DOCKPIPE_GO_SDK_ARCHIVE=/absolute/path/sdk.tar.gz
export DOCKPIPE_GO_SDK_MANIFEST_SHA256=<independently-trusted-digest>
export GO_EXECUTABLE=/absolute/path/to/supported/go
dockpipe --workflow-file workflows/test/config.yml
```

`build` skips tests; `test` runs both Go module suites and builds four helper binaries.
`test.integration` additionally requires `DORKPIPE_TEST_PIPEON_SOURCE`, the absolute
explicit Pipeon package source root. Ordinary tests keep that cross-repository lane
separate. Native SQLite evidence still requires its own opt-in/host qualification.
The two modules consume the extracted SDK through temporary module files, never an
implicit sibling DockPipe source directory. Candidate attempts and caches are scoped
artifacts. The `package.candidate` workflow prepares tested Linux amd64 tools in its owned
artifact scope. `package.compile` exercises those source hooks and compiles only the package's
resolver root and `packages/dorkpipe/workflows`. Each attempt selects a fresh packages
root under its artifact scope, then exports all slices from that isolated store. The
validator requires exactly the eight resolver and eighteen workflow identities declared
in `release/package-ownership.json`, version 0.6.5 and namespace `dockpipeproject`.
It checks archive manifests, sizes, digests, checksum sidecars and exact output files;
core and root maintainer workflows fail validation. `store.path` identifies only the
last validated attempt. A compatible released compiler is required for hosted proof. Source-build and resolver consumer hooks verify that preparation
against the current source inventory, locks, target and binary checksums. They
require explicit preparation and perform no dependency downloads. Consumer
compilation also requires `DOCKPIPE_RELEASE_ARCHIVE`, the local archive matching
the committed CLI lock. Other targets fail explicitly until qualified.

The manual `sdk.candidate` workflow fetches the exact public GitHub release declared
in `release/sdk-source.lock.json` without requiring credentials. An optional `GH_TOKEN` authenticates GitHub API requests.
CI supplies `${{ github.token }}` with `contents: read`; no URL or digest dispatch inputs
are accepted. The source descriptor pins the repository, release tag and both asset
names; `release/dependencies.lock.json` independently pins their bytes and source identity.
The downloader authenticates only to `api.github.com`, follows bounded HTTPS redirects
to GitHub asset storage without credentials, and verifies both assets and the SDK
inventory before any Go execution. It then removes the token from the build environment,
explicitly downloads public Go dependencies with checksum verification, and tests/builds
offline. The candidate also runs the DorkPipe shell suite in an isolated fixture made
from the verified SDK, tracked package source, test-only Go workspace files and prepared
tools. Its per-attempt fixture inventory and result are included with the Go candidate
delivery and checksums. The ordinary shell lane does not import a sibling Pipeon checkout;
`test.integration` remains the separate explicit Pipeon source lane. Local `build`, `test`
and `package.candidate` input paths remain supported.

The public SDK release is selected entirely by `release/sdk-source.lock.json` and
`release/dependencies.lock.json`. Provision its exact approved manifest and source
archive before running hosted candidates. Preserve the original source commit,
source inventory, inherited LICENSE and applicable third-party notices. A public
redistribution has its own approved manifest and immutable release identity; the
historical private SDK release and its assets remain unchanged. A manifest change
requires a new committed manifest digest, even when archive bytes are unchanged.
Anonymous fetching supports public consumers; an explicit token remains supported
and is sent only to the initial GitHub API request, never asset-storage redirects.
Inspect actual download, test and uploaded receipts before claiming qualification.
Downloading a checksummed SDK does not authorize package-feed publication.

Hosted workflows read the exact CLI archive URL, version and checksum from
`release/toolchains.lock.json`. Bootstrap verifies and extracts the archive before
execution. SDK selections must match `release/dependencies.lock.json`, including
version, source commit, inventory, manifest and archive digests. Upgrade these
committed locks and rerun consumer checks together. Official Actions references also
pin verified full commit SHAs. Hosted SDK/editor candidate qualification remains pending. Inspect
`.github/workflows/` before dispatch.

A local checksummed Go compatibility SDK has qualified both module suites and the four
helper binaries. This does not qualify package delivery or a protected native ABI.
Public redistribution preserves inherited Apache-2.0 rights and provenance obligations.

Go CI uploads a curated archive containing the four helper binaries, candidate receipt
and inherited LICENSE, plus archive checksums. Extracted SDK trees, test caches and
temporary module files stay outside that upload. Native/debug hardening and catalog
ingestion remain separate qualification work.

The current resolver manifests and CLI lock require DockPipe 0.6.17. Both are
pinned inputs; local artifact-consumer evidence does not establish remote install,
upgrade or rollback qualification. Controlled package-feed consumers must pin the
immutable published version and archive digest after its release is qualified.

The Go candidate workflow also runs `editor.candidate`, `package.compile` and
`package.delivery` against the pinned CLI and approved SDK. `package.delivery` accepts
only the validator's exact 26-leaf Linux amd64 store and the two editor VSIXs whose
bytes match `extensions.json`. It freezes `dorkpipe-packages-0.6.5-linux-amd64.tar.gz`
with the inherited LICENSE, both VSIXs, and a deterministic
`dockpipe-language-test-sdk-0.0.2.tar.gz` containing the ten curated language-support
source files and their `editor-source.json` receipt. `delivery-provenance.json` and
`SHA256SUMS` cover all four assets outside the validated store. A staging-branch push
uploads those exact files to the
public prerelease `v0.6.5-staging.<source SHA prefix>`. The release points at the
full source commit and cannot replace an existing asset with different bytes.
Publication retries compare all remote bytes before accepting an existing release.
The published release is not marked latest. Production promotion should select the
exact qualified archive and checksums from this immutable staging release; rebuilding
from a branch or selecting a mutable latest release would change the candidate.

Both release publishers require GitHub metadata identifying exactly
`Dockpipe-Industries/dorkpipe` with `private: false` and `visibility: public`.
Malformed or mismatched metadata fails before release writes or asset consumption.
Staging and master package-host promotion preserve their existing environment gates
and immutable candidate/release paths. Frozen historical 0.6.4 assets stay unchanged;
public package candidates use 0.6.5 and retain the existing editor identities/versions.

Production package-host publication is manual. Select `master` when dispatching
the delivery workflow and explicitly set `publish_production` to true. It defaults
to false; pushes, pull requests and changing the default branch do not publish
production. The existing `release` environment gate and frozen source-pin validation
still apply. A valid `release/package-host-source.lock.json` and qualified payloads
are required before a future production dispatch. Staging publication is unchanged.
