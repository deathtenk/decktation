#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"

rm -rf "$SCRIPT_DIR/runtime" "$SCRIPT_DIR/defaults"
mkdir -p "$SCRIPT_DIR/runtime" "$SCRIPT_DIR/defaults"

cp "$REPO_ROOT/runtime/pyproject.toml" "$SCRIPT_DIR/runtime/"
cp "$REPO_ROOT/runtime/uv.lock" "$SCRIPT_DIR/runtime/"
cp "$REPO_ROOT/runtime/decktation-runtime.spec" "$SCRIPT_DIR/runtime/"
cp "$REPO_ROOT/runtime/runtime_entry.py" "$SCRIPT_DIR/runtime/"
cp -R "$REPO_ROOT/runtime/src" "$SCRIPT_DIR/runtime/"
cp -R "$REPO_ROOT/defaults/." "$SCRIPT_DIR/defaults/"
cp "$REPO_ROOT/plugin.json" "$SCRIPT_DIR/plugin.json"
