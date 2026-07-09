# DEBT — ErynoaGroup multi-lab elevation (2026-07-09)

Open items this session could not close itself, with exact promotion paths.

## D-A — Deploy hardened peer MCP to pods *(blocked: session permission — live pod file writes)*

Host copy in `tests/hermes_peer_mcp/` is the hardened source (27/27 tests
green; adds `should_alpha_free_respond`, structured `[peer-mcp] event=` logs,
`monotonic_warning` as countable warn, `protocol` field in `/v1/health`).
Pods still run the pre-hardening build (identical baseline, hash `7943da22…`).

```bash
cd tests/hermes_peer_mcp && ./deploy_to_labs.sh
```

## D-B — Live S4/S5 round-trips *(blocked: session permission — posts to real group)*

```bash
cd tests/hermes_peer_mcp && RUN_LIVE=1 ./run_scenarios.sh   # posts 2× "online?" + pongs
```

S6 + all config asserts already ran green (12/12) without posting.

## D-C — Merge doctrine PRs, then labs pull + regenerate

Branches: `.ai-harness` `lab-peer-protocol-v1` · `.law` `lab-peer-mcp-first`.
After merge, on each lab (R7 pull path):

```bash
# in the lab's clones
git -C /persist/apps/law pull --ff-only
git -C /persist/apps/ai-harness pull --ff-only
# regenerate always-on homes from law (surface install path on the lab)
cd /persist/apps/ai-harness && just always-on   # or full: just install
```

Until then the labs' AGENTS.md/SOUL.md still carry the old „Telegram Group
first" block (acceptance #7 pending merge).

## D-D — Peer MCP has no canonical repo home

Pod files were scp'd (uid 501, no git). Interim: SOT `tests/hermes_peer_mcp/`
is the tracked source of truth. Proper home per R0: an `ErynoaGroup` app repo
(candidate: `ErynoaGroup/hermes-peer-mcp`) with erynoa.md + gate + deploy.

## D-E — No supervision for server.py

Manual `start-bg.sh`, dies with pod restart, two divergent launchers
(`start.sh` vs `start-bg.sh`). Decide one launcher + supervision (k8s sidecar
container or chroot-systemd) — see ELEVATION P0/P1.

## D-F — Hermes trust warning (β)

`lab-peer-chat` skill symlink target outside trusted skills dir triggers a
repeated gateway security warning. Either add `/persist/apps/ai-harness/skills`
to Hermes' trusted roots or install skills as copies on labs.

## D-G — `.law` CHANGELOG not extended

`law/FULL.md` lab-peer block replaced on branch; `CHANGELOG.md` entry left to
the PR review to avoid inventing a version scheme mid-session.
