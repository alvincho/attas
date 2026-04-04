#!/bin/zsh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

DEFAULT_LOCAL_CONFIG="prompits/examples/plaza.agent"

export PROMPITS_BIND_HOST="${PROMPITS_BIND_HOST:-127.0.0.1}"

if [[ -z "${PROMPITS_AGENT_CONFIG:-}" ]]; then
  export PROMPITS_AGENT_CONFIG="$DEFAULT_LOCAL_CONFIG"
  export PROMPITS_PORT="${PROMPITS_PORT:-8211}"
  export PROMPITS_PUBLIC_URL="${PROMPITS_PUBLIC_URL:-http://127.0.0.1:8211}"
else
  export PROMPITS_AGENT_CONFIG
fi

exec python3 prompits/create_agent.py --config "$PROMPITS_AGENT_CONFIG"
