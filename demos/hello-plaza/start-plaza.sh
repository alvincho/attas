#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
cd "$ROOT_DIR"

exec python3 prompits/create_agent.py --config demos/hello-plaza/plaza.agent
