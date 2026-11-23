#!/usr/bin/env bash
# Push selected keys from .env to the Vercel project's environment.
#
# Reads DEPLOY_ENV_VARS (space-separated key names) and VERCEL_ENV from the
# environment; the Makefile sets both. Values are never printed.
#
# KEYCARD_ZONE_URL comes from .env. The deployed application authenticates
# with Vercel's OIDC workload identity, so KEYCARD_CLIENT_SECRET stays local.
# KEYCARD_WORKLOAD_CLIENT_ID, when set, is pushed as KEYCARD_CLIENT_ID.

set -euo pipefail

# Keep the Vercel CLI from opening any interactive prompt.
export CI=1

. "$(dirname "$0")/env-file.sh"

VERCEL_ENV="${VERCEL_ENV:-production}"
DEPLOY_ENV_VARS="${DEPLOY_ENV_VARS:-}"

if ! command -v vercel >/dev/null 2>&1; then
  echo "vercel not found. Install it with: npm i -g vercel" >&2
  exit 1
fi

if [ -z "${DEPLOY_ENV_VARS// /}" ]; then
  echo "DEPLOY_ENV_VARS is empty, so there is nothing to push."
  echo "Set it in the Makefile once you know which keys the deployment needs."
  exit 0
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "$ENV_FILE not found. Run \`keycard new mcp\` to create it." >&2
  exit 1
fi

# Every vercel subcommand below prompts to create a project when the directory
# is not linked, which would hang this script. Check for the link up front.
if [ ! -f "${VERCEL_PROJECT_FILE:-.vercel/project.json}" ]; then
  echo "This directory is not linked to a Vercel project. Run: vercel link" >&2
  exit 1
fi

status=0

push() {
  local key="$1" value="$2"

  # Vercel has no upsert, so remove any existing value first. A missing key is
  # not an error here.
  vercel env rm "$key" "$VERCEL_ENV" --yes </dev/null >/dev/null 2>&1 || true

  if printf '%s' "$value" | vercel env add "$key" "$VERCEL_ENV" >/dev/null 2>&1; then
    echo "  set   $key -> $VERCEL_ENV"
  else
    echo "  fail  $key (vercel env add rejected it)"
    status=1
  fi
}

for key in $DEPLOY_ENV_VARS; do
  value="$(read_value "$key")"

  if [ -z "$value" ]; then
    echo "  skip  $key (not set in $ENV_FILE)"
    status=1
    continue
  fi

  push "$key" "$value"
done

# The deployed server reads KEYCARD_CLIENT_ID, but in .env that name holds the
# local client-secret credential's ID, which Keycard rejects from Vercel. The
# workload client ID gets its own key so the two can't be confused.
workload_client_id="$(read_value KEYCARD_WORKLOAD_CLIENT_ID)"
if [ -n "$workload_client_id" ]; then
  push KEYCARD_CLIENT_ID "$workload_client_id"
else
  echo "  skip  KEYCARD_CLIENT_ID (add KEYCARD_WORKLOAD_CLIENT_ID to $ENV_FILE once Keycard shows it after you register the deployment)"
fi

if [ "$status" -eq 0 ]; then
  if [ -n "$workload_client_id" ]; then
    echo "Env is set. Deploy for it to take effect: vercel deploy --prod"
  else
    echo "KEYCARD_CLIENT_ID is not set, so a v2 workload credential will reject deployed tool calls with invalid_client. Add KEYCARD_WORKLOAD_CLIENT_ID to $ENV_FILE and run make env-push again before deploying."
  fi
fi

exit $status
