#!/usr/bin/env bash

dorkpipe_test_init_sdk() {
	local root="${1:?repo root}"
	local selected_binary="${DOCKPIPE_TEST_DOCKPIPE_BIN:-${DOCKPIPE_BIN:-}}"
	local sdk_exports
	if [[ -z "$selected_binary" ]]; then
		printf 'Select an installed DockPipe with DOCKPIPE_TEST_DOCKPIPE_BIN or DOCKPIPE_BIN.\n' >&2
		return 1
	fi
	selected_binary="$(command -v "$selected_binary")" || return 1
	export DOCKPIPE_TEST_DOCKPIPE_BIN="$selected_binary"
	export DOCKPIPE_BIN="$selected_binary"
	sdk_exports="$("$selected_binary" sdk --workdir "$root")" || return 1
	eval "$sdk_exports"
}

dorkpipe_test_tool_is_runnable() {
	local tool="${1:?tool}"
	shift || true
	command -v "$tool" >/dev/null 2>&1 || return 1
	"$tool" "$@" >/dev/null 2>&1
}

dorkpipe_test_require_go() {
	if ! dorkpipe_test_tool_is_runnable go version; then
		echo "${1:-dorkpipe package test}: Go is required but not runnable" >&2
		exit 1
	fi
}

dorkpipe_test_init_go_cache() {
	local root="${1:?repo root}"
	local caller_script_dir="${DOCKPIPE_SCRIPT_DIR:-}"
	local caller_workdir="${DOCKPIPE_WORKDIR:-}"
	dorkpipe_test_init_sdk "$root"
	if [[ -n "$caller_script_dir" ]]; then
		export DOCKPIPE_SCRIPT_DIR="$caller_script_dir"
	fi
	if [[ -n "$caller_workdir" ]]; then
		export DOCKPIPE_WORKDIR="$caller_workdir"
	fi
	export GOCACHE="${GOCACHE:-$(dockpipe_sdk path build go-cache)}"
	export GOTMPDIR="${GOTMPDIR:-$(dockpipe_sdk path build go-tmp)}"
	mkdir -p "$GOCACHE" "$GOTMPDIR"
}

dorkpipe_test_tmp_root() {
	local root="${1:?repo root}"
	dorkpipe_test_init_sdk "$root"
	local tmp_root="${DORKPIPE_PACKAGE_TEST_TMPDIR:-$(dockpipe_sdk path state tmp package-tests)}"
	mkdir -p "$tmp_root"
	printf '%s\n' "$tmp_root"
}

dorkpipe_test_mktemp_dir() {
	local root="${1:?repo root}"
	local tmp_root
	tmp_root="$(dorkpipe_test_tmp_root "$root")"
	mktemp -d "${tmp_root}/tmp.XXXXXXXXXX"
}

dorkpipe_test_assert() {
	local root="${1:?repo root}"
	shift
	dorkpipe_test_require_go "dorkpipe_test_assert"
	dorkpipe_test_init_go_cache "$root"
	(
		cd "$root/packages/dorkpipe/lib"
		go run ./cmd/test-assert "$@"
	)
}
