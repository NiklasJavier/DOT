# Scenario suite — ErynoaGroup multi-lab OS (protocol v1)

Executable evidence for the address calculus (protocol §3) and the peer
bridge (§6). Runner: [`run_scenarios.sh`](./run_scenarios.sh).

| Mode | What runs |
|---|---|
| `./run_scenarios.sh` | config asserts A1–A4 + guard scenario S6 (no group posts) |
| `RUN_LIVE=1 ./run_scenarios.sh` | additionally S4 + S5 — **posts real messages** to ErynoaGroup |

## Scenarios

| ID | Action | Expect | Automation |
|----|--------|--------|------------|
| S1 | Human plain „wie geht's" | α answers; β observe-only | **log grep** (below) — human input can't be automated |
| S2 | Human exclusive `@erynoa_beta_hermes_bot` | α silent (drop in log); β answers | **log grep** (below) |
| S3 | Human „frag beta online" (no @) | α answers + `tag_peer`; β posts plain pong | semi-manual: human sends text, then S4 mechanics apply |
| S4 | `tag_peer` α→β („online?") | result `as=alpha`, peer part `as=beta`, both posted, no `α:`/`β:` in bodies | **automated** (`RUN_LIVE=1`) |
| S5 | `tag_peer` β→α | symmetric | **automated** (`RUN_LIVE=1`) |
| S6 | wake with wrong `expect_lab` | HTTP 409, **no post** | **automated** (default) |
| S7 | identity swap (wrong bot token) | getMe reject before any post | **documented** — guard `_assert_local_bot_token` runs on every post; injecting a foreign token is not safely automatable |

## Config asserts (always run)

| ID | Assert | Enforces |
|---|---|---|
| A1 | α `.env` has exactly `TELEGRAM_FREE_RESPONSE_CHATS=-5535276728` | T1 leader |
| A2 | β `.env` has **no** `TELEGRAM_FREE_RESPONSE_CHATS` | one leader only |
| A3 | both: `REQUIRE_MENTION=true` + `EXCLUSIVE_BOT_MENTIONS=true` | T2/T3/T5/T6 |
| A4 | `/v1/health` per pod: `lab_id` own, `remote` other, `anti_swap` true | §1 identity |

## S1/S2 log-grep recipes (evidence, not automation)

```bash
# S1 — after a plain human message: alpha answered, beta only observed
kubectl exec -n labs lab-alpha-0 -c lab -- \
  grep -E 'inbound message:' /persist/rootfs/root/.hermes/logs/gateway.log | tail -3
kubectl exec -n labs lab-beta-0 -c lab -- \
  grep -E 'observed \(no bot' /persist/rootfs/root/.hermes/logs/gateway.log | tail -3

# S2 — after a human message that ONLY @-mentions beta:
# alpha log shows drop/observe (exclusive), beta log shows inbound + response
kubectl exec -n labs lab-alpha-0 -c lab -- \
  grep -E 'exclusive|observed \(no bot' /persist/rootfs/root/.hermes/logs/gateway.log | tail -3
```

Post-deploy (once the hardened `server.py` runs on the pods), the peer MCP
additionally emits countable `[peer-mcp] event=` lines:
`event=wake|post|reject|warn` with `as= target= path=fast|llm self_mid= peer_mid=`.
