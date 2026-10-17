#!/usr/bin/env python3
"""Prepare the fixed local package candidate; dependency downloads are opt-in."""
import argparse
from pathlib import Path
import tempfile

import candidate_contract
import go_candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--manifest-sha256', help='Optional assertion; must equal the source lock')
    parser.add_argument('--go', default='go')
    parser.add_argument('--download-dependencies', action='store_true')
    args = parser.parse_args()
    args.source = Path(__file__).resolve().parents[1]
    lock = candidate_contract.read_json(args.source / 'release/dependencies.lock.json', go_candidate.MAX_LOCK_BYTES)
    pinned_digest = lock['dockpipe_go_sdk']['manifest_sha256']
    if args.manifest_sha256 is not None and args.manifest_sha256 != pinned_digest:
        parser.error('Manifest digest assertion differs from the committed source lock')
    args.manifest_sha256 = pinned_digest
    args.output = candidate_contract.prepared_directory(args.source)
    args.tests = True
    if args.output.exists() or args.output.is_symlink():
        if not args.output.is_dir() or any(path.is_symlink() for path in (args.output, *args.output.parents)):
            parser.error('Existing preparation must be an unlinked owned directory')
        previous = Path(tempfile.mkdtemp(prefix='previous.', dir=args.output.parent))
        args.output.rename(previous / 'prepared')
        print(f'Previous preparation retained: {previous}')
    go_candidate.build(args)


if __name__ == '__main__':
    main()
