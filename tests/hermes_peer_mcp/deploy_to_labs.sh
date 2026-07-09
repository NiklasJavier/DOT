#!/usr/bin/env bash
# Deploy the hardened peer MCP (peer_model.py, server.py, tests) to both lab
# pods, run the unit tests there, restart the server, verify health.
# Run from tests/hermes_peer_mcp/. Requires kubectl access to ns "labs".
set -euo pipefail

NS="${NS:-labs}"
DIR=/persist/apps/hermes-peer-mcp
VENV_PY=/persist/rootfs/usr/local/lib/hermes-agent/venv/bin/python
FILES=(peer_model.py server.py test_peer_mcp_model.py)

for pod in lab-alpha-0 lab-beta-0; do
  echo "== $pod: backup + copy =="
  for f in "${FILES[@]}"; do
    kubectl exec -n "$NS" "$pod" -c lab -- bash -c \
      "cp $DIR/$f $DIR/$f.bak-\$(date +%Y%m%d) 2>/dev/null || true"
    kubectl exec -i -n "$NS" "$pod" -c lab -- bash -c "cat > $DIR/$f" < "$f"
  done

  echo "== $pod: unit tests on pod =="
  kubectl exec -n "$NS" "$pod" -c lab -- bash -c \
    "cd $DIR && rm -rf __pycache__ && $VENV_PY -m unittest test_peer_mcp_model 2>&1 | tail -2"

  echo "== $pod: restart peer MCP =="
  kubectl exec -n "$NS" "$pod" -c lab -- bash -c \
    "cd $DIR && kill \$(cat server.pid) 2>/dev/null || true; sleep 1; ./start-bg.sh; sleep 2"

  echo "== $pod: health (expect protocol=1.0.0) =="
  kubectl exec -n "$NS" "$pod" -c lab -- bash -c \
    "chroot /persist/rootfs bash -lc 'python3 -c \"import urllib.request;print(urllib.request.urlopen(\\\"http://127.0.0.1:8755/v1/health\\\",timeout=5).read().decode())\"'"
done

echo "== done. Now: RUN_LIVE=1 ./run_scenarios.sh for S4/S5 =="
