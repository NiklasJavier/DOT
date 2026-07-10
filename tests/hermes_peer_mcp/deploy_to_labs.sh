#!/usr/bin/env bash
# Deploy the hardened peer MCP (peer_model.py, server.py, tests, start-bg) to
# both lab pods, run unit tests there, restart the server, verify health.
# Run from tests/hermes_peer_mcp/. Requires kubectl access to ns "labs".
set -euo pipefail

NS="${NS:-labs}"
DIR=/persist/apps/hermes-peer-mcp
ROOTFS=/persist/rootfs
VENV_PY=/usr/local/lib/hermes-agent/venv/bin/python
FILES=(peer_model.py server.py test_peer_mcp_model.py start-bg.sh)

for pod in lab-alpha-0 lab-beta-0; do
  echo "== $pod: backup + copy =="
  for f in "${FILES[@]}"; do
    kubectl exec -n "$NS" "$pod" -c lab -- bash -c \
      "cp $DIR/$f $DIR/$f.bak-\$(date +%Y%m%d) 2>/dev/null || true"
    kubectl exec -i -n "$NS" "$pod" -c lab -- bash -c "cat > $DIR/$f" < "$f"
  done
  kubectl exec -n "$NS" "$pod" -c lab -- bash -c "chmod +x $DIR/start-bg.sh"

  echo "== $pod: unit tests on pod (chroot + hermes venv) =="
  kubectl exec -n "$NS" "$pod" -c lab -- bash -c \
    "chroot $ROOTFS bash -lc 'cd $DIR && rm -rf __pycache__ && $VENV_PY -m unittest test_peer_mcp_model 2>&1' | tail -5"

  echo "== $pod: restart peer MCP =="
  # NOTE: do not pkill -f 'python ./server.py' from a command that embeds that
  # string — the shell wrapper matches itself and gets SIGTERM (exit 143).
  kubectl exec -n "$NS" "$pod" -c lab -- bash -c "
    set -e
    cd $DIR
    if [[ -f server.pid ]]; then
      old=\$(cat server.pid)
      kill \"\$old\" 2>/dev/null || true
      sleep 1
      kill -9 \"\$old\" 2>/dev/null || true
    fi
    fuser -k 8755/tcp 2>/dev/null || true
    sleep 1
    ./start-bg.sh
    sleep 2
    if [[ -f server.pid ]]; then
      echo \"pid=\$(cat server.pid)\"
      ps -p \"\$(cat server.pid)\" -o pid,cmd= || true
    fi
  "

  echo "== $pod: health (expect protocol=1.0.0) =="
  # retry a few times — uvicorn bind can lag a second
  ok=0
  for i in 1 2 3 4 5; do
    if body=$(kubectl exec -n "$NS" "$pod" -c lab -- bash -c \
      "chroot $ROOTFS bash -lc 'python3 -c \"import urllib.request;print(urllib.request.urlopen(\\\"http://127.0.0.1:8755/v1/health\\\",timeout=5).read().decode())\"'" \
      2>/dev/null); then
      echo "$body"
      ok=1
      break
    fi
    echo "  health attempt $i failed, sleep 2"
    sleep 2
  done
  [[ "$ok" == "1" ]] || { echo "FATAL: health failed on $pod"; exit 1; }
done

echo "== done. Now: RUN_LIVE=1 ./run_scenarios.sh for S4/S5 =="
