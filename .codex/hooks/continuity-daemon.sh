#!/usr/bin/env bash
# Refresh continuity self-state. Intended to be run periodically.

set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
REPO_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="${CODEX_ENV_FILE:-$REPO_DIR/.env}"

if ! command -v bun >/dev/null 2>&1; then
  exit 0
fi

cd "$REPO_DIR"
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi
GARMIN_TOKENSTORE="${GARMINTOKENS:-${GARMIN_TOKENSTORE:-$HOME/.garminconnect}}"
GARMIN_ALLOW_PASSWORD_LOGIN="${CODEX_GARMIN_ALLOW_PASSWORD_LOGIN_IN_HOOK:-0}"
if command -v uv >/dev/null 2>&1 \
  && [ -f "$REPO_DIR/scripts/fetch-garmin-companion-biometrics.py" ] \
  && {
    [ -e "$GARMIN_TOKENSTORE/oauth1_token.json" ] && [ -e "$GARMIN_TOKENSTORE/oauth2_token.json" ] || \
    {
      [ "$GARMIN_ALLOW_PASSWORD_LOGIN" = "1" ] && \
      [ -n "${GARMIN_EMAIL:-}" ] && [ -n "${GARMIN_PASSWORD:-}" ]
    }
  }
then
  uv run "$REPO_DIR/scripts/fetch-garmin-companion-biometrics.py" >/dev/null 2>&1 || true
fi
bun run ./scripts/continuity-daemon.ts tick >/dev/null
