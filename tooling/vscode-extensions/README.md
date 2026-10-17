# DorkPipe editor extensions

This repository owns Dockpipe Language Support and the DorkPipe companion
(current extension identity `dorkpipe.pipeon`). Keep those published identities.
Pipeon product development is paused; retaining its editor source does not enable
publication or an automatic install.

Install locked build dependencies with `npm ci` in each extension directory, then
run `bash tooling/vscode-extensions/scripts/build.sh /absolute/artifact-directory`
from the repository root. This runs the language tests, TypeScript compilation,
webview smoke checks and produces versioned VSIX files with a checksum manifest.
No Dockpipe checkout is required to build the extensions. At runtime they use the
installed Dockpipe CLI and the separately installed DorkPipe/MCP packages.

Consumers supply the exact VSIX files and expected digests through their package
pipeline. The candidate CI uploads review artifacts only; production catalog and
marketplace publication remain separate, licensed release operations.
