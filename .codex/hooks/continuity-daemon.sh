#!/usr/bin/env bash
# Refresh continuity self-state. Intended to be run periodically.

set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
REPO_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)"

if ! command -v bun >/dev/null 2>&1; then
  exit 0
fi

cd "$REPO_DIR"
bun run ./scripts/continuity-daemon.ts tick >/dev/null
