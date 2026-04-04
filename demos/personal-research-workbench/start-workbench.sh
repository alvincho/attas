#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
cd "$ROOT_DIR"

HOST=${PHEMACAST_PERSONAL_AGENT_HOST:-127.0.0.1}
PORT=${PHEMACAST_PERSONAL_AGENT_PORT:-8041}
MAP_PHEMAR_CONFIG_PATH=${PHEMACAST_MAP_PHEMAR_CONFIG_PATH:-"$ROOT_DIR/demos/personal-research-workbench/map_phemar.phemar"}
MAP_PHEMAR_POOL_PATH=${PHEMACAST_MAP_PHEMAR_POOL_PATH:-"$ROOT_DIR/demos/personal-research-workbench/map_phemar_pool"}

export PHEMACAST_MAP_PHEMAR_CONFIG_PATH="$MAP_PHEMAR_CONFIG_PATH"
export PHEMACAST_MAP_PHEMAR_POOL_PATH="$MAP_PHEMAR_POOL_PATH"

if [ "${PHEMACAST_PERSONAL_AGENT_RELOAD:-0}" = "1" ]; then
  exec python3 -m uvicorn phemacast.personal_agent.app:app --host "$HOST" --port "$PORT" --reload
fi

exec python3 -m uvicorn phemacast.personal_agent.app:app --host "$HOST" --port "$PORT"
