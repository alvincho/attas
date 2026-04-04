#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname "$0")/../../.." && pwd)
cd "$ROOT_DIR"

HOST=${PHEMACAST_PERSONAL_AGENT_HOST:-127.0.0.1}
PORT=${PHEMACAST_PERSONAL_AGENT_PORT:-8061}

if [ "${PHEMACAST_PERSONAL_AGENT_RELOAD:-0}" = "1" ]; then
  exec python3 -m uvicorn phemacast.personal_agent.app:app --host "$HOST" --port "$PORT" --reload
fi

exec python3 -m uvicorn phemacast.personal_agent.app:app --host "$HOST" --port "$PORT"
