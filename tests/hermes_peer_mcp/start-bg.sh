#!/usr/bin/env bash
# Launch peer MCP in background. Safe to call from outside the lab rootfs:
# re-execs into chroot so hermes-agent venv python (uv symlink) resolves.
set -euo pipefail

DIR=/persist/apps/hermes-peer-mcp
ROOTFS=/persist/rootfs
VENV_PY=/usr/local/lib/hermes-agent/venv/bin/python
HERMES_ENV=/root/.hermes/.env

# Outside rootfs → re-exec inside chroot (venv python only works there).
if [[ ! -x "$VENV_PY" ]]; then
  if [[ ! -d "$ROOTFS/usr/local/lib/hermes-agent/venv" ]]; then
    echo "fatal: hermes venv not found under $ROOTFS" >&2
    exit 1
  fi
  # shellcheck disable=SC2093
  exec chroot "$ROOTFS" bash -lc "cd $DIR && exec ./start-bg.sh"
fi

cd "$DIR"
# shellcheck disable=SC1091
source ./env
if [[ -f "$HERMES_ENV" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$HERMES_ENV"
  set +a
fi
export HOME="${HOME:-/root}"
export PATH="/usr/local/lib/hermes-agent/venv/bin:/usr/local/bin:${PATH}"
export HERMES_BIN="${HERMES_BIN:-/usr/local/lib/hermes-agent/venv/bin/hermes}"

# Detach: parent records pid; child becomes the server.
if [[ "${PEER_MCP_FOREGROUND:-0}" != "1" ]]; then
  nohup "$VENV_PY" ./server.py >>"$DIR/server.log" 2>&1 &
  echo $! >"$DIR/server.pid"
  echo "started pid=$(cat "$DIR/server.pid") lab=${LAB_ID:-?} port=${PEER_MCP_PORT:-8755}"
  exit 0
fi

exec "$VENV_PY" ./server.py
