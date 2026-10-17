# Standalone DorkPipe package-host delivery

`package.host` validates one frozen DorkPipe package delivery and, with explicit
publication mode, writes immutable objects to the existing package host. The producer
remains the public, qualified GitHub release. The publisher downloads its exact six
assets and verifies the source commit, asset digests, `SHA256SUMS` and provenance
before any R2 write. It does not build packages.

The publisher safely extracts the bundle, validates all 26 compiled package
archives and checksum sidecars against the source-owned store contract, and
publishes them at `<prefix>/packages/`. The installable
`packages-store-manifest.json` is uploaded last; the original frozen bundle
and its six release assets remain byte-identical.

Staging pushes run the qualified package candidate and public-release publisher
first, then publish those same bytes beneath
`packages/standalone/dorkpipe/candidates/0.6.5-staging.<source12>/` through the
`release-staging` environment. The manual `go-candidate.yml` dispatch on `staging` requires an exact frozen-release
pin in `release/package-host-source.lock.json`; it fails closed until the new 0.6.5
release is qualified and that lock is recorded. It does not rebuild pinned bytes. Master pushes run
the candidate check and promote only the pinned frozen release beneath
`packages/standalone/dorkpipe/releases/0.6.5/` through the `release` environment.
`js/dev` and `dev` validate their local frozen deliveries only.

The two VSIXs and ten-file language test SDK are included because they are already
qualified delivery dependencies for Pipeon editor consumption and retirement proof.
No source archive, build Go SDK, mutable `latest.json`, shared APT path or catalog
pointer is written. Existing keys must contain identical bytes; uploads use atomic
`If-None-Match: *` and read back each object. Configure the two existing scoped R2
credentials as `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in the corresponding
GitHub environment, with `DOCKPIPE_RELEASE_BUCKET` and HTTPS `R2_ENDPOINT_URL` as
variables. This workflow does not provision credentials or buckets.
