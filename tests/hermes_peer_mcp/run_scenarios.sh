#!/usr/bin/env bash
# Scenario harness — ErynoaGroup multi-lab OS (protocol v1). See scenarios.md.
# Default: config asserts + S6 guard (no group posts).
# RUN_LIVE=1: adds S4/S5 tag_peer round-trips — POSTS REAL MESSAGES to ErynoaGroup.
set -uo pipefail

NS="${NS:-labs}"
PASS=0 FAIL=0

chk() { # name want got
  if [[ "$3" == "$2" ]]; then echo "PASS $1"; ((PASS++)); else echo "FAIL $1  want=[$2] got=[$3]"; ((FAIL++)); fi
}
chk_contains() { # name needle haystack
  if [[ "$3" == *"$2"* ]]; then echo "PASS $1"; ((PASS++)); else echo "FAIL $1  missing=[$2]"; ((FAIL++)); fi
}
chk_absent() { # name needle haystack
  if [[ "$3" != *"$2"* ]]; then echo "PASS $1"; ((PASS++)); else echo "FAIL $1  forbidden=[$2] present"; ((FAIL++)); fi
}

pod_env_grep() { # pod pattern -> count
  kubectl exec -n "$NS" "$1" -c lab -- bash -c \
    "chroot /persist/rootfs bash -lc 'grep -cE \"$2\" /root/.hermes/.env'" 2>/dev/null | tr -d '[:space:]'
}

pod_py() { # pod python-src (runs inside chroot with peer MCP env sourced)
  kubectl exec -i -n "$NS" "$1" -c lab -- bash -c \
    "chroot /persist/rootfs bash -lc 'set -a; source /persist/apps/hermes-peer-mcp/env; set +a; python3 -'" <<< "$2" 2>/dev/null
}

post_json() { # pod url json-payload -> "HTTP_CODE|body"
  pod_py "$1" "
import json, os, urllib.request, urllib.error
req = urllib.request.Request(
    '$2', data=json.dumps($3).encode(),
    headers={'Content-Type': 'application/json',
             'Authorization': 'Bearer ' + os.environ['PEER_MCP_TOKEN']},
    method='POST')
try:
    with urllib.request.urlopen(req, timeout=120) as r:
        print(str(r.status) + '|' + r.read().decode())
except urllib.error.HTTPError as e:
    print(str(e.code) + '|' + (e.read().decode() if e.fp else ''))
"
}

get_health() { # pod url -> body
  pod_py "$1" "
import os, urllib.request
req = urllib.request.Request('$2', headers={'Authorization': 'Bearer ' + os.environ['PEER_MCP_TOKEN']})
print(urllib.request.urlopen(req, timeout=10).read().decode())
"
}

echo "== A: config asserts =="
chk A1-alpha-free-response 1 "$(pod_env_grep lab-alpha-0 '^TELEGRAM_FREE_RESPONSE_CHATS=-5535276728$')"
chk A2-beta-no-free-response 0 "$(pod_env_grep lab-beta-0 '^TELEGRAM_FREE_RESPONSE_CHATS')"
chk A3-alpha-mention-gates 2 "$(pod_env_grep lab-alpha-0 '^TELEGRAM_(REQUIRE_MENTION|EXCLUSIVE_BOT_MENTIONS)=true$')"
chk A3-beta-mention-gates 2 "$(pod_env_grep lab-beta-0 '^TELEGRAM_(REQUIRE_MENTION|EXCLUSIVE_BOT_MENTIONS)=true$')"

echo "== A4: identity health =="
ah="$(get_health lab-alpha-0 http://127.0.0.1:8755/v1/health)"
bh="$(get_health lab-beta-0 http://127.0.0.1:8755/v1/health)"
chk_contains A4-alpha-id '"lab_id":"alpha"' "$ah"
chk_contains A4-alpha-remote '"remote":"beta"' "$ah"
chk_contains A4-alpha-antiswap '"anti_swap":true' "$ah"
chk_contains A4-beta-id '"lab_id":"beta"' "$bh"
chk_contains A4-beta-remote '"remote":"alpha"' "$bh"
chk_contains A4-beta-antiswap '"anti_swap":true' "$bh"

echo "== S6: wrong expect_lab -> 409, no post =="
r6a="$(post_json lab-alpha-0 http://127.0.0.1:8755/v1/ask_group '{"prompt":"scenario S6 guard check","expect_lab":"beta"}')"
chk S6-alpha-409 409 "${r6a%%|*}"
r6b="$(post_json lab-beta-0 http://127.0.0.1:8755/v1/ask_group '{"prompt":"scenario S6 guard check","expect_lab":"alpha"}')"
chk S6-beta-409 409 "${r6b%%|*}"

if [[ "${RUN_LIVE:-0}" == "1" ]]; then
  echo "== S4: tag_peer alpha -> beta (LIVE group post) =="
  r4="$(post_json lab-alpha-0 http://127.0.0.1:8755/v1/tag_peer '{"ask":"online?"}')"
  b4="${r4#*|}"
  chk S4-http-200 200 "${r4%%|*}"
  chk_contains S4-as-alpha 'as=alpha' "$b4"
  chk_contains S4-peer-as-beta 'as=beta' "$b4"
  chk_contains S4-self-posted 'message_id=' "$b4"
  chk_absent S4-no-alpha-badge '\\u03b1:' "$b4"
  chk_absent S4-no-beta-badge '\\u03b2:' "$b4"

  echo "== S5: tag_peer beta -> alpha (LIVE group post) =="
  r5="$(post_json lab-beta-0 http://127.0.0.1:8755/v1/tag_peer '{"ask":"online?"}')"
  b5="${r5#*|}"
  chk S5-http-200 200 "${r5%%|*}"
  chk_contains S5-as-beta 'as=beta' "$b5"
  chk_contains S5-peer-as-alpha 'as=alpha' "$b5"
  chk_contains S5-self-posted 'message_id=' "$b5"
  chk_absent S5-no-alpha-badge '\\u03b1:' "$b5"
  chk_absent S5-no-beta-badge '\\u03b2:' "$b5"
else
  echo "== S4/S5 skipped (set RUN_LIVE=1 to post real group messages) =="
fi

echo
echo "== result: PASS=$PASS FAIL=$FAIL =="
[[ "$FAIL" == "0" ]]
