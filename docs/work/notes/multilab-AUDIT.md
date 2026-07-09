# AUDIT — ErynoaGroup Multi-Lab OS (W0 reality lock)

**Date:** 2026-07-09 · **Auditor:** Mython (Claude) · **Gate:** G0
**Scope:** lab-alpha-0 / lab-beta-0 (ns `labs`), peer MCP :8755, skill `lab-peer-chat`,
always-on AGENTS/SOUL, Agent Surface `ErynoaGroup/.ai-harness`, law `ErynoaGroup/.law`,
host tests `SOT/tests/hermes_peer_mcp/`, gateway logs 13:53–19:12 (full retention, <6 h).
**Method:** 5 parallel inventory agents + inline kubectl probes; hashes via sha256.

---

## 1. Artifact matrix

| Artifact | α (lab-alpha-0) | β (lab-beta-0) | Surface (origin/main) | Drift? |
|---|---|---|---|---|
| `.env` telegram flags | require_mention=true · observe=true · allow_bots=all · exclusive_bot_mentions=true · free_response_chats=-5535276728 | same **minus** free_response | n/a (not in SSOT) | ✓ matches brief intent · ✗ not codified (D3) |
| `config.yaml` telegram | mirrors .env; allow_from = Niklas+both bots | same | n/a | ✓ |
| `config.yaml` mcp_servers | peer-beta → http://lab-beta:8755/mcp · peer-local → 127.0.0.1:8755 | peer-alpha/peer-local symmetric | n/a | ✓ (shared bearer token both entries) |
| skill `lab-peer-chat` | SKILL.md `107b9387…` + references/{protocol,host-setup}.md + scripts | **identical hashes** | **identical after `git pull`** (was 2 behind) | ✓ parity; content defects D2/D3 |
| always-on AGENTS.md/SOUL.md SSOT block | generated from `.law` `law/FULL.md` §275 | identical block | source: `ErynoaGroup/.law` | ✗ **D1 — wrong doctrine** |
| SOUL persona | α „Ziel-Führer / Continuity-Anker" | β „Craft-Peer / Hands-on-Spezialist, gleichrangig, spricht bei @/Wake/tag_peer" | hand-written per lab (not in SSOT) | ✓ roles correct |
| peer MCP code | server.py `7943da22…` peer_model `c5e02612…` | identical | n/a (untracked anywhere) | ✗ D4/D5 — host copy stale, no repo provenance |
| peer MCP health | local ✓ · α→β ✓ | local ✓ · β→α ✓ | — | ✓ anti_swap=true both |
| peer MCP launcher | manual `start-bg.sh`, root pid, no supervision | same | — | ✗ D6 |
| host tests (SOT) | — | — | 11/11 green (unittest) | ✗ D4 (server.py differs), coverage gaps D7 |

## 2. Drift register (owner file paths)

| # | Drift | Owner / fix site | Workstream |
|---|---|---|---|
| **D1** | `.law` `law/FULL.md` §275 „Lab peer — **Telegram Group first**": claims bot→bot `@` wakes peer, mandates visible `PEER α→β:` badge lines, `ALLOW_BOTS=mentions`, MCP as fallback only. All four contradict live config + working bridge; block also self-contradicts SOUL Stil-Regel 4 (no badges). Generated into every lab's AGENTS.md+SOUL.md. | `ErynoaGroup/.law` → `law/FULL.md` (labs regenerate via R7 pull) | W2 |
| **D2** | `references/protocol.md` is 16 lines: no actor table, no address truth table, no silence/leadership laws, no memory-continuity rule, no versioning. Wording „natural `@peer …`" invites the dead-end Telegram-@ pattern. | `.ai-harness` `skills/lab-peer-chat/references/protocol.md` | W1/W2 |
| **D3** | `references/host-setup.md` shows only shared flags — missing the α/β split (`free_response_chats` α-only, no-free-response β) and `exclusive_bot_mentions`; no assertable checklist. | `.ai-harness` `skills/lab-peer-chat/references/host-setup.md` | W2/W3 |
| **D4** | Host `SOT/tests/hermes_peer_mcp/server.py` (`713370f1…`) behind pods (`7943da22…`) — pods have newer `systemish` prompt in `ask_agent_group`. | SOT `tests/hermes_peer_mcp/server.py` (sync from pod, then harden) | W3 |
| **D5** | Peer MCP code has no git home: pod files uid 501 (scp'd from workstation), two divergent launchers (`start.sh` vs `start-bg.sh`). | track in SOT + document deploy in host-setup | W3 + DEBT |
| **D6** | No supervision: server.py = manually started root process; dies on pod restart. | `start-bg.sh` + DEBT (proper unit out of session scope) | W5/DEBT |
| **D7** | `peer_model.py`: no `should_alpha_free_respond`; logging exists only as tool **return strings** (no stderr log lines); monotonic message-id check is a return-string warning invisible to monitoring; tests miss reply-to, explicit_mentions, both-mentioned, plain-text-negative rows. | SOT `tests/hermes_peer_mcp/` + pods | W3 |
| **D8** | Doctrine `ALLOW_BOTS=mentions` vs live `all`. Telegram never delivers bot→bot group messages regardless, so the flag is inert for the peer path. Decision: **keep `all`**, codify in host-setup, delete the `mentions` claim (comes with D1). | `.law` + host-setup | W2 |
| **D9** | Hermes security warning on β: skill outside trusted dir (`/root/.hermes/skills` symlink → `/persist/apps/ai-harness/...`). | lab install path | DEBT |
| **D10** | Goal continuity: 3 synchronized session_reset pairs in window; α's „own the goal" has no durable store. | protocol §9 + W3 item 4 | W1/W3 |
| **D11** | Ops churn: 24 gateway restarts/pod in 5.5 h; log retention < 6 h; two aborted `tag_peer` calls (interrupted by next user message). | risk register / observability | W5 |

## 3. Chat-behavior evidence (group −5535276728, 15:57–19:12, 63 turn events)

| Pattern | Count | Note |
|---|---|---|
| β answered unaddressed plain text | 1 (15:57) | first turn of window; clean afterwards (23 correct observe-only suppressions) |
| Forbidden `α:`/`β:`/`Beta:` prefixes in outbound | ≥6 | lower bound (visible only via reply_to quotes) |
| Peer wake attempted via Telegram `@` (dead end) | ≥3 | α×2, β×1 — never woke the peer; human relayed by hand |
| Correct MCP `tag_peer` uses | 2 | **both interrupted** („user sent a new message", 148.8 s / 40.4 s) |
| Too-long answers (small ask, ≥1.8 k chars) | 3 | incl. 2 057 chars for a 4-word follow-up |
| Dropped/unanswered human messages | ~5 | 2 lost to restarts/stuck run |
| session_reset pairs | 3 | 17:47 · 17:56 · 18:39 |

Most violations date 16:00–17:45 — before the current SKILL.md generation landed. The live
config intent itself is **correct**; the failures are doctrine (D1/D2) + runtime discipline (D7/D10).

## 4. G0 verdict

**PASS** — all drifts enumerated with owner paths. No blocker: cluster, Surface clone,
`.law` clone, and host tests all reachable/verified. Proceed W1.
