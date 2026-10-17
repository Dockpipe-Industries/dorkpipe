#!/usr/bin/env python3
"""Install the source-locked Linux amd64 hosted bootstrap CLI from its archive."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile
from urllib.parse import urlsplit


MAX_LOCK_BYTES = 64 << 10
MAX_ARCHIVE_BYTES = 128 << 20
MAX_EXECUTABLE_BYTES = 256 << 20


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate source lock field")
        result[key] = value
    return result


def load_lock(path):
    with path.open("rb") as stream:
        data = stream.read(MAX_LOCK_BYTES + 1)
    if len(data) > MAX_LOCK_BYTES:
        raise ValueError("Toolchain lock exceeds 64 KiB")
    document = json.loads(data, object_pairs_hook=unique_keys)
    if not isinstance(document, dict) or type(document.get("schema")) is not int or document["schema"] != 1:
        raise ValueError("Expected toolchain lock schema 1")
    lock = document.get("dockpipe")
    fields = {"version", "platform", "format", "url", "sha256"}
    if not isinstance(lock, dict) or set(lock) not in (fields, fields | {"release_tag"}):
        raise ValueError("Incomplete or unknown DockPipe lock fields")
    if not all(isinstance(value, str) for value in lock.values()):
        raise ValueError("DockPipe lock fields must be strings")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", lock["version"]):
        raise ValueError("DockPipe lock requires a numeric release version")
    if lock["platform"] != "linux-amd64" or lock["format"] != "tar.gz":
        raise ValueError("Bootstrap requires the Linux amd64 tar.gz release")
    url = urlsplit(lock["url"])
    if url.scheme != "https" or not url.hostname or url.username is not None or url.password is not None or url.query or url.fragment:
        raise ValueError("DockPipe lock URL must be HTTPS without credentials, query, or fragment")
    release_tag = lock.get("release_tag", f"v{lock['version']}")
    expected_tag = re.escape(f"v{lock['version']}") + r"(?:-staging\.[0-9]+\.[0-9]+\.[0-9a-f]{12})?"
    if not re.fullmatch(expected_tag, release_tag):
        raise ValueError("Release tag must identify the pinned version and immutable candidate")
    expected_path = f"/Dockpipe-Industries/dockpipe/releases/download/{release_tag}/dockpipe_{lock['version']}_linux_amd64.tar.gz"
    if url.netloc != "github.com" or url.path != expected_path:
        raise ValueError("DockPipe lock URL must identify the matching immutable release archive")
    if not re.fullmatch(r"[0-9a-f]{64}", lock["sha256"]):
        raise ValueError("DockPipe lock requires a lowercase SHA-256 digest")
    for variable, field in [("DOCKPIPE_CLI_URL", "url"), ("DOCKPIPE_CLI_SHA256", "sha256")]:
        if variable in os.environ and os.environ[variable] != lock[field]:
            raise ValueError(f"{variable} differs from the committed toolchain lock")
    return lock


def extract_executable(archive, destination):
    # Read the fixed header directly. Generic tar readers may allocate unbounded
    # GNU/PAX extension metadata before returning their first visible member.
    with gzip.open(archive, "rb") as stream:
        header = stream.read(512)
        if len(header) != 512:
            raise ValueError("Release archive has no complete tar header")
        member = tarfile.TarInfo.frombuf(header, "utf-8", "strict")
        if member.name != "dockpipe" or member.type not in {tarfile.REGTYPE, tarfile.AREGTYPE} or member.linkname:
            raise ValueError("Release archive must contain one regular dockpipe member")
        if member.size <= 0 or member.size > MAX_EXECUTABLE_BYTES:
            raise ValueError("DockPipe executable exceeds its 256 MiB size contract")
        with destination.open("xb") as output:
            remaining = member.size
            while remaining:
                block = stream.read(min(1 << 20, remaining))
                if not block:
                    raise ValueError("Truncated release executable")
                output.write(block)
                remaining -= len(block)
        padding_size = (-member.size) % 512
        if stream.read(padding_size) != b"\0" * padding_size:
            raise ValueError("Release archive has invalid member padding")
        # Standard tar records are 10 KiB. After the sole member, only the two
        # zero end blocks and record padding are accepted, with bounded inflate.
        tail = stream.read(10241)
        if len(tail) < 1024 or len(tail) > 10240 or any(tail):
            raise ValueError("Release archive contains unlisted members or invalid termination")
    destination.chmod(0o755)


def export_paths(executable, archive=None):
    # Open both destinations before writing either. On write failure, restore
    # their previous lengths so a failed bootstrap does not export a stale path.
    with Path(os.environ["GITHUB_ENV"]).open("a+") as environment:
        with Path(os.environ["GITHUB_PATH"]).open("a+") as paths:
            environment.seek(0, os.SEEK_END)
            paths.seek(0, os.SEEK_END)
            environment_length = environment.tell()
            paths_length = paths.tell()
            try:
                environment.write(f"DOCKPIPE_BIN={executable}\n")
                if archive is not None:
                    environment.write(f"DOCKPIPE_RELEASE_ARCHIVE={archive}\n")
                paths.write(f"{executable.parent}\n")
                environment.flush()
                paths.flush()
            except BaseException:
                environment.seek(environment_length)
                environment.truncate()
                paths.seek(paths_length)
                paths.truncate()
                raise


def bootstrap(lock_path, keep_archive=False):
    lock = load_lock(lock_path)
    if platform.system() != "Linux" or platform.machine() not in {"x86_64", "amd64"}:
        raise ValueError("Hosted bootstrap supports only Linux amd64")
    required = ["RUNNER_TEMP", "GITHUB_ENV", "GITHUB_PATH"]
    if any(not os.environ.get(name) for name in required):
        raise ValueError("RUNNER_TEMP, GITHUB_ENV, and GITHUB_PATH are required")
    install = Path(tempfile.mkdtemp(prefix="dockpipe-cli.", dir=os.environ["RUNNER_TEMP"]))
    try:
        if "\n" in str(install) or "\r" in str(install):
            raise ValueError("Runner path contains an unsafe line break")
        archive = install / "release.tar.gz"
        subprocess.run([
            "curl", "--fail", "--location", "--proto", "=https", "--proto-redir", "=https",
            "--connect-timeout", "15", "--max-time", "120", "--max-filesize", str(MAX_ARCHIVE_BYTES),
            "--output", str(archive), lock["url"],
        ], check=True, timeout=125)
        if archive.stat().st_size > MAX_ARCHIVE_BYTES:
            raise ValueError("Release archive exceeds 128 MiB")
        checksum = hashlib.sha256()
        with archive.open("rb") as stream:
            for block in iter(lambda: stream.read(1 << 20), b""):
                checksum.update(block)
        if checksum.hexdigest() != lock["sha256"]:
            raise ValueError("Release archive SHA-256 does not match the source lock")
        executable = install / "dockpipe"
        extract_executable(archive, executable)
        if not keep_archive:
            archive.unlink()
        # Export only after every archive and identity check has succeeded.
        export_paths(executable, archive if keep_archive else None)
    except BaseException:
        shutil.rmtree(install)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--keep-archive", action="store_true", help="Retain verified archive for offline consumer compilation")
    args = parser.parse_args()
    try:
        bootstrap(args.lock, args.keep_archive)
    except (OSError, EOFError, ValueError, TypeError, RecursionError, tarfile.TarError, subprocess.SubprocessError) as error:
        parser.exit(1, f"DockPipe bootstrap failed: {error}\n")


if __name__ == "__main__":
    main()
