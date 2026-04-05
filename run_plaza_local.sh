#!/bin/zsh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

if [[ "$#" -eq 0 ]]; then
  exec python3 -m prompits.cli up desk
fi

exec python3 -m prompits.cli "$@"
