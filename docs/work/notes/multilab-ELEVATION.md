# ELEVATION — ErynoaGroup multi-lab OS (decisions + 48h backlog)

**Date:** 2026-07-09 · **Gate:** G5 · Decisions below are chosen, not options.
Evidence base: [multilab-AUDIT.md](./multilab-AUDIT.md) · protocol v1 in
`.ai-harness` `skills/lab-peer-chat/references/protocol.md`.

## 1. Latency budget — alpha free-response (decision)

Measured today: small talk 3.6–75 s, worst turn 782 s (13 api_calls for 247
chars), pings ~1 s via fast path.

| Context | Budget (p50 / p95) | Mechanism |
|---|---|---|
| Group small talk / ack | 5 s / 15 s | depth policy §8 L2 (≤2 sentences ⇒ few tokens) |
| Group substantive | 20 s / 60 s | cap group runs: `HERMES_MAX_ITERATIONS≈6` for the gateway session; long jobs → 1-sentence ack, work in background, report when done |
| Peer wake (llm path) | 15 s / 45 s | `PEER_ASK_TIMEOUT=45`, `PEER_ASK_MAX_ITER=2` (already live) |
| Ping | 1 s | `is_fast_ping` fast path (already live) |

Tool-loops in group turns (782 s case: `skill_manage` retry loop) are the #1
latency killer — the same_tool_failure_halt did fire; budget assumes it stays.

## 2. γ onboarding template (decision: address-only joiner)

Protocol §11.3 governs. Concretely for a new lab `gamma`:

1. **Identity:** create `@erynoa_gamma_hermes_bot`, record bot id.
2. **Code:** extend `peer_model.py` `_PEER_DEFAULTS` + `_ALIASES` with gamma.
   ⚠ today's map is **pairwise** (one `remote_*` per lab) — multi-peer needs
   the P1 refactor below before a 3rd lab actually joins.
3. **Host profile** (address-only — γ is never leader):
   `TELEGRAM_REQUIRE_MENTION=true`, `TELEGRAM_EXCLUSIVE_BOT_MENTIONS=true`,
   `TELEGRAM_OBSERVE_UNMENTIONED_GROUP_MESSAGES=true`, **no**
   `TELEGRAM_FREE_RESPONSE_CHATS`; `allow_from` += gamma id on α/β (and vice
   versa); `mcp_servers` += `peer-gamma` on α/β, γ gets `peer-alpha`/`peer-beta`.
4. **Doctrine:** SOUL persona file; always-on comes from `.law` unchanged;
   `specialist.md` applies as-is.
5. **Verify:** health identity, S6 guard, then live pings.

## 3. Observability (decision: log-derived counters first, no new stack)

One dashboard (start as a `just`/cron script emitting a table, not Grafana):

| Metric | Source |
|---|---|
| messages/min + chars/turn per bot | gateway.log `response ready` lines |
| peer wake latency | `[peer-mcp] event=wake` → `event=post` delta (post-deploy) |
| exclusive drops | gateway.log exclusive/observed lines |
| session_resets + gateway restarts | gateway.log banners (24 restarts/5.5 h today!) |
| monotonic warns / rejects | `[peer-mcp] event=warn|reject` counts |

Ship as `P2` script `tests/hermes_peer_mcp/peer_metrics.sh`; revisit a real
exporter only if the labs outgrow log-grep.

## 4. Risk register

| Risk | Likelihood | Mitigation (state) |
|---|---|---|
| Alpha double-speak (summarizes/impersonates β) | med | protocol §8 L3/L4 + S-α2; guards block posting *as* β (live). Monitor via S-α2 log review |
| Goal loss on session_reset | high (3 pairs/day) | §9 memory convention (doctrine landed; behavior check = P0 below) |
| Surface/doctrine drift labs vs SSOT | med | R7 pull + STALE flags; drift is detectable lab-side only — D-C debt |
| Token/latency cost of free-response | med | depth policy L2 + budget §1; watch chars/turn metric |
| Peer MCP process dies (no supervision) | **high** | D-E debt — P0 below |
| Gateway restart churn (24/5.5 h) | high | P1 investigation below |
| Log retention < 6 h kills forensics | med | P1 logrotate/persist below |

## 5. Next-48h backlog (any agent: Grok or Claude)

**P0**
1. Run `deploy_to_labs.sh` + `RUN_LIVE=1 run_scenarios.sh` (D-A/D-B, human-gated).
2. Merge `.ai-harness#lab-peer-protocol-v1` + `.law#lab-peer-mcp-first`; labs
   pull + `just always-on` (D-C) → acceptance #7 closes.
3. Supervision for peer MCP: pick **one** launcher (`start-bg.sh`), add a
   liveness loop (k8s-side restart or cron `pgrep || start-bg.sh`) (D-E).
4. Verify alpha actually writes `## GROUP GOAL` memory on goal change (§9) —
   one live probe after next reset.

**P1**
5. Multi-peer refactor of `peer_model.py` (peer *set*, not pairwise remote) —
   prerequisite for γ; keep the same guard functions.
6. Investigate gateway restart churn (24/pod/5.5 h) — config-reload loop vs
   crash; fix or document.
7. Gateway log rotation → persist 7 days (`/persist/rootfs/root/.hermes/logs/`).
8. Group-turn iteration cap for alpha (latency budget §1 knob).
9. Hermes trusted-skills root for `/persist/apps/ai-harness/skills` (D-F).

**P2**
10. `peer_metrics.sh` counters table (§3).
11. Migrate peer MCP into `ErynoaGroup/hermes-peer-mcp` app repo (D-D, R0).
12. S1/S2 semi-automation: scripted human-message prompts + log assertions.
