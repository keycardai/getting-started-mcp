#!/usr/bin/env bash
# Stage selected keys from .env as Fly secrets for the next `fly machine run`.
#
# Reads DEPLOY_ENV_VARS (space-separated key names) from the environment; the
# Makefile sets it. .env's KEYCARD_CLIENT_ID belongs to the local credential and
# is never staged; the Machine's KEYCARD_CLIENT_ID is the workload client ID,
# which the console's Deploy step sets after you register the deployment.
# Nothing is staged unless every value is set.

set -euo pipefail

. "$(dirname "$0")/env-file.sh"

DEPLOY_ENV_VARS="${DEPLOY_ENV_VARS:-}"

if ! command -v fly >/dev/null 2>&1; then
  echo "fly not found. Install it with: brew install flyctl" >&2
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "$ENV_FILE not found. Run \`keycard new mcp\` to create it." >&2
  exit 1
fi

if [ -z "${DEPLOY_ENV_VARS// /}" ]; then
  echo "DEPLOY_ENV_VARS is empty, so there is nothing to stage."
  exit 0
fi

secrets=()
missing=0
for key in $DEPLOY_ENV_VARS; do
  value="$(read_value "$key")"

  if [ -z "$value" ]; then
    echo "  missing  $key (not set in $ENV_FILE)" >&2
    missing=1
    continue
  fi

  secrets+=("$key=$value")
done

if [ "$missing" -ne 0 ]; then
  echo "Nothing staged. Add the missing keys to $ENV_FILE and run make fly-secrets again." >&2
  exit 1
fi

fly secrets set --stage "${secrets[@]}"
