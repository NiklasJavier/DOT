#!/usr/bin/env python3
"""Peer Hermes MCP — natural group chat with hard anti-swap identity guards.

Rule: every Telegram post is checked against getMe vs expected bot for HOST_ID.
Every remote wake is checked: remote health lab_id must be expected peer, never self.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from peer_model import (
    PROTOCOL_VERSION,
    assert_bot_matches_lab,
    assert_peer_pair,
    assert_remote_health,
    clean_chat_text,
    fast_pong_text,
    format_chat_outbound,
    format_chat_reply,
    is_addressed_to,
    is_fast_ping,
    monotonic_warning,
    parse_message_id,
    resolve_me,
    validate_nonempty,
)

_VENV_SITE = "/usr/local/lib/hermes-agent/venv/lib/python3.11/site-packages"
if _VENV_SITE not in sys.path and os.path.isdir(_VENV_SITE):
    sys.path.insert(0, _VENV_SITE)

from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

HOST_ID = (os.environ.get("LAB_ID") or os.environ.get("PEER_MCP_HOST_ID") or socket.gethostname()).strip().lower()
PORT = int(os.environ.get("PEER_MCP_PORT", "8755"))
TOKEN = os.environ.get("PEER_MCP_TOKEN", "").strip()
HERMES_BIN = os.environ.get("HERMES_BIN", "hermes")
PEER_ASK_MODEL = os.environ.get("PEER_ASK_MODEL", "grok-4.5")
PEER_ASK_TIMEOUT = int(os.environ.get("PEER_ASK_TIMEOUT", "45"))
PEER_ASK_MAX_ITER = os.environ.get("PEER_ASK_MAX_ITER", "2")

ME = resolve_me(HOST_ID)
SELF_BOT = ME.get("bot", "")
SELF_NAME = ME.get("name", HOST_ID)
SELF_BOT_ID = ME.get("bot_id", "")
REMOTE_URL = (ME.get("remote_url") or "").rstrip("/")
REMOTE_ID = ME.get("remote_id") or ""
REMOTE_BOT = ME.get("remote_bot") or ""
REMOTE_NAME = ME.get("remote_name") or REMOTE_ID

# Fail fast at import if map is inconsistent
_pair_err = assert_peer_pair(HOST_ID, REMOTE_ID) if REMOTE_ID else f"error: no remote for {HOST_ID}"
if _pair_err:
    print(f"[peer-hermes-mcp] FATAL map: {_pair_err}", file=sys.stderr)

mcp = FastMCP(
    f"peer-hermes-{HOST_ID}",
    instructions=(
        f"Lab '{HOST_ID}' (@{SELF_BOT}). Natural chat. Anti-swap identity guards on. "
        f"Remote must be {REMOTE_ID}. tag_peer wakes peer only. Rule1: only answer if addressed."
    ),
    host="0.0.0.0",
    port=PORT,
)
mcp.settings.host = "0.0.0.0"
mcp.settings.port = PORT
try:
    mcp.settings.transport_security.enable_dns_rebinding_protection = False
except Exception:
    pass


class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in ("/health", "/v1/health"):
            return await call_next(request)
        if not TOKEN:
            return await call_next(request)
        auth = request.headers.get("authorization", "")
        if auth.strip() != f"Bearer {TOKEN}":
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return await call_next(request)


def _log(event: str, **fields: Any) -> None:
    """One structured line per event to stderr — greppable, countable.

    Vocabulary: event=wake|post|reject|warn|error · as=<lab> · target=<lab> ·
    path=fast|llm · self_mid/peer_mid=<message_id>.
    """
    kv = " ".join(f"{k}={v}" for k, v in fields.items() if v is not None and v != "")
    print(f"[peer-mcp] event={event} as={HOST_ID} {kv}".rstrip(), file=sys.stderr, flush=True)


def _load_hermes_env() -> dict[str, str]:
    out: dict[str, str] = {}
    p = Path("/root/.hermes/.env")
    if not p.exists():
        return out
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _telegram_get_me(bot_token: str) -> dict[str, Any]:
    req = urllib.request.Request(f"https://api.telegram.org/bot{bot_token}/getMe", method="GET")
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    if not data.get("ok"):
        return {}
    return data.get("result") or {}


def _assert_local_bot_token(bot_token: str) -> str | None:
    """Hard anti-swap: token must belong to THIS lab's bot only."""
    try:
        me = _telegram_get_me(bot_token)
    except Exception as e:
        return f"error: getMe failed: {e}"
    uname = me.get("username") or ""
    tid = str(me.get("id") or "")
    err = assert_bot_matches_lab(HOST_ID, uname)
    if err:
        return err
    if SELF_BOT_ID and tid and tid != SELF_BOT_ID:
        return (
            f"error: identity mismatch — lab={HOST_ID} expects bot_id={SELF_BOT_ID}, "
            f"token is id={tid}"
        )
    return None


def _telegram_post(text: str, reply_to_message_id: int | None = None) -> str:
    env = _load_hermes_env()
    bot = env.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat = (
        env.get("TELEGRAM_HOME_CHANNEL")
        or env.get("TELEGRAM_GROUP_ALLOWED_CHATS")
        or os.environ.get("TELEGRAM_HOME_CHANNEL", "")
    )
    if "," in chat:
        chat = chat.split(",")[0].strip()
    if not bot or not chat or chat == "*":
        return "error: missing TELEGRAM_BOT_TOKEN or TELEGRAM_HOME_CHANNEL"

    id_err = _assert_local_bot_token(bot)
    if id_err:
        return id_err

    if text.strip().startswith("@"):
        body_text = " ".join(text.split())[:4000]
    else:
        body_text = format_chat_reply(text)[:4000]

    payload: dict[str, Any] = {
        "chat_id": chat,
        "text": body_text,
        "disable_web_page_preview": "true",
    }
    if reply_to_message_id:
        payload["reply_to_message_id"] = str(int(reply_to_message_id))
        payload["allow_sending_without_reply"] = "true"
    data = urllib.parse.urlencode(payload).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{bot}/sendMessage",
        data=data,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = json.loads(resp.read().decode())
        if not raw.get("ok"):
            return f"error: telegram {raw}"
        result = raw.get("result") or {}
        mid = result.get("message_id")
        # Telegram also returns from.username — verify speaker again
        from_u = ((result.get("from") or {}).get("username") or "").lower()
        if from_u and from_u != SELF_BOT.lower():
            return (
                f"error: post speaker mismatch — expected @{SELF_BOT}, telegram from=@{from_u} "
                f"message_id={mid}"
            )
        return f"posted chat={chat} message_id={mid} as={HOST_ID} bot=@{SELF_BOT}"
    except Exception as e:
        return f"error: telegram post failed: {e}"


def _run_hermes(prompt: str) -> str:
    env = {
        **os.environ,
        "HERMES_ACCEPT_HOOKS": "1",
        "HERMES_MAX_ITERATIONS": PEER_ASK_MAX_ITER,
        "HOME": os.environ.get("HOME", "/root"),
    }
    cmd = [
        HERMES_BIN, "-z", str(prompt).strip(),
        "--cli", "-m", PEER_ASK_MODEL,
        "--ignore-rules", "--yolo",
    ]
    try:
        out = subprocess.check_output(
            cmd, text=True, timeout=PEER_ASK_TIMEOUT, stderr=subprocess.STDOUT, env=env,
        )
        return (out or "").strip() or "…"
    except subprocess.TimeoutExpired:
        return f"error: peer timed out after {PEER_ASK_TIMEOUT}s"
    except subprocess.CalledProcessError as e:
        return f"error (exit {e.returncode}):\n{(e.output or '')[:1500]}"
    except Exception as e:
        return f"error: {e}"


def _http_json(url: str, payload: dict[str, Any] | None = None, timeout: int = 90, method: str = "POST") -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    data = None if payload is None or method == "GET" else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return {"error": f"HTTP {e.code}: {body[:400]}"}
    except Exception as e:
        return {"error": str(e)}


def _verify_remote_or_error() -> str | None:
    """Anti-swap: remote health must be expected peer lab."""
    if not REMOTE_URL:
        return "error: PEER_REMOTE_URL empty"
    pair = assert_peer_pair(HOST_ID, REMOTE_ID)
    if pair:
        return pair
    health = _http_json(f"{REMOTE_URL}/v1/health", payload=None, timeout=10, method="GET")
    if "error" in health and "lab_id" not in health:
        return f"error: remote health failed: {health.get('error')}"
    rid = str(health.get("lab_id") or "")
    return assert_remote_health(HOST_ID, rid)


@mcp.tool()
def peer_identity() -> str:
    return (
        f"lab_id={HOST_ID}\nname={SELF_NAME}\nbot=@{SELF_BOT}\nbot_id={SELF_BOT_ID}\n"
        f"remote={REMOTE_ID}\nremote_bot=@{REMOTE_BOT}\nremote_url={REMOTE_URL}\n"
        f"anti_swap=getMe+remote_health\nrule1=is_addressed_to"
    )


@mcp.tool()
def peer_status() -> str:
    return (
        f"lab_id={HOST_ID}\nok=true\nremote={REMOTE_ID}\n"
        f"ask_model={PEER_ASK_MODEL}\ntimeout={PEER_ASK_TIMEOUT}\n"
        f"tools=tag_peer,ask_agent_group,group_say,am_i_addressed"
    )


@mcp.tool()
def am_i_addressed(text: str, reply_to_is_self: bool = False) -> str:
    hit = is_addressed_to(text, HOST_ID, reply_to_is_self=bool(reply_to_is_self))
    return f"lab={HOST_ID}\naddressed={'yes' if hit else 'no'}\ntext={clean_chat_text(text)[:200]}"


@mcp.tool()
def ask_agent(prompt: str) -> str:
    err = validate_nonempty(prompt, "prompt")
    if err:
        return err
    return _run_hermes(str(prompt).strip())


@mcp.tool()
def group_say(text: str) -> str:
    err = validate_nonempty(text, "text")
    if err:
        return err
    return _telegram_post(format_chat_reply(text))


@mcp.tool()
def ask_agent_group(prompt: str, reply_to_message_id: int | None = None, from_lab: str | None = None) -> str:
    """Answer in-group as THIS bot only (never posts as peer)."""
    err = validate_nonempty(prompt, "prompt")
    if err:
        return err
    # Reject self-wake / wrong initiator (anti-swap / loop)
    if from_lab:
        fl = str(from_lab).strip().lower()
        if fl == HOST_ID:
            _log("reject", reason="self_wake", from_lab=fl)
            return f"error: refused self-wake from_lab={fl} host={HOST_ID}"
        if fl and fl != REMOTE_ID:
            _log("reject", reason="wrong_from_lab", from_lab=fl, expected=REMOTE_ID)
            return f"error: refused wake from unexpected lab={fl} (expected peer={REMOTE_ID})"
    ask = clean_chat_text(prompt)
    t0 = time.time()

    if is_fast_ping(ask):
        reply = fast_pong_text(HOST_ID)
        post = _telegram_post(reply, reply_to_message_id=reply_to_message_id)
        _log(
            "post", path="fast", from_lab=from_lab, reply_to=reply_to_message_id,
            self_mid=parse_message_id(post), elapsed_s=f"{time.time()-t0:.1f}",
        )
        return (
            f"as={HOST_ID}\nbot=@{SELF_BOT}\nreply={reply}\n{post}\n"
            f"elapsed_s={time.time()-t0:.1f}\npath=fast_ping"
        )

    systemish = (
        f"You are the Telegram bot {SELF_NAME} in group ErynoaGroup. "
        f"Never claim to be {REMOTE_NAME}. You were addressed. "
        f"Write like a normal chat message only: max 2 short sentences. "
        f"Do NOT prefix with alpha/beta/α/β/lab marks. Do NOT use PEER frames. "
        f"No tools, no meta, no signature.\n\nMessage:\n{ask}"
    )
    reply = _run_hermes(systemish)
    elapsed = time.time() - t0
    if reply.startswith("error"):
        _log("error", path="llm", from_lab=from_lab, detail=reply.splitlines()[0][:120])
        return f"as={HOST_ID}\n{reply}\nelapsed_s={elapsed:.1f}"
    body = format_chat_reply(reply)
    post = _telegram_post(body, reply_to_message_id=reply_to_message_id)
    _log(
        "post", path="llm", from_lab=from_lab, reply_to=reply_to_message_id,
        self_mid=parse_message_id(post), chars=len(body), elapsed_s=f"{elapsed:.1f}",
    )
    return (
        f"as={HOST_ID}\nbot=@{SELF_BOT}\nreply={body}\n{post}\n"
        f"elapsed_s={elapsed:.1f}\npath=llm"
    )


@mcp.tool()
def tag_peer(ask: str) -> str:
    """Post as THIS bot, wake REMOTE peer only — never answers as the peer."""
    err = validate_nonempty(ask, "ask")
    if err:
        return err
    pair = assert_peer_pair(HOST_ID, REMOTE_ID)
    if pair:
        return pair
    remote_err = _verify_remote_or_error()
    if remote_err:
        return remote_err

    ask_s = clean_chat_text(ask)
    line = format_chat_outbound(ask_s, peer_bot=REMOTE_BOT, peer_name=REMOTE_NAME)
    # Must @ the REMOTE bot only
    if REMOTE_BOT and f"@{REMOTE_BOT}" not in line and REMOTE_BOT not in line:
        line = f"@{REMOTE_BOT} {line}"

    post_self = _telegram_post(line)
    if post_self.startswith("error"):
        _log("error", reason="self_post_failed", target=REMOTE_ID)
        return f"as={HOST_ID}\nself={post_self}"
    mid = parse_message_id(post_self)
    _log("wake", target=REMOTE_ID, self_mid=mid)

    payload: dict[str, Any] = {
        "prompt": ask_s,
        "from_lab": HOST_ID,
        "expect_lab": REMOTE_ID,
    }
    if mid:
        payload["reply_to_message_id"] = mid

    r = _http_json(
        f"{REMOTE_URL}/v1/ask_group",
        payload,
        timeout=PEER_ASK_TIMEOUT + 25,
    )
    if "error" in r and "result" not in r:
        return f"as={HOST_ID}\nself={post_self}\nerror: remote wake failed: {r.get('error')}"

    peer_result = str(r.get("result") or r)
    peer_lab = str(r.get("lab_id") or "")
    if peer_result.startswith("error") or "error:" in peer_result.split("\n", 1)[0]:
        return f"as={HOST_ID}\ntarget={REMOTE_ID}\nself={post_self}\npeer={peer_result}"
    # Anti-swap: response must be from remote lab
    if peer_lab and peer_lab != REMOTE_ID:
        return (
            f"as={HOST_ID}\nself={post_self}\n"
            f"error: remote answered as lab_id={peer_lab} expected={REMOTE_ID} (swap blocked)\n"
            f"peer_raw={peer_result[:300]}"
        )
    if f"as={HOST_ID}" in peer_result and f"as={REMOTE_ID}" not in peer_result:
        # peer should tag itself as remote
        if peer_result.startswith("as=") and f"as={REMOTE_ID}" not in peer_result.split("\n", 1)[0]:
            return (
                f"as={HOST_ID}\nself={post_self}\n"
                f"error: peer result speaker mismatch (swap blocked)\npeer_raw={peer_result[:300]}"
            )
    # Prefer explicit as=REMOTE_ID in body
    if "as=" in peer_result and f"as={REMOTE_ID}" not in peer_result:
        return (
            f"as={HOST_ID}\nself={post_self}\n"
            f"error: peer result missing as={REMOTE_ID} (swap blocked)\npeer_raw={peer_result[:300]}"
        )

    peer_mid = parse_message_id(peer_result)
    warn = monotonic_warning(mid, peer_mid)
    if warn:
        # Accept but escalate: countable log line for monitoring, flag in result
        _log("warn", reason="monotonic", target=REMOTE_ID, self_mid=mid, peer_mid=peer_mid)
        return (
            f"as={HOST_ID}\ntarget={REMOTE_ID}\nself={post_self}\n"
            f"peer={peer_result}\n{warn}"
        )

    return f"as={HOST_ID}\ntarget={REMOTE_ID}\nself={post_self}\npeer={peer_result}"


async def _health(_request: Request) -> JSONResponse:
    return JSONResponse({
        "ok": True,
        "protocol": PROTOCOL_VERSION,
        "lab_id": HOST_ID,
        "name": SELF_NAME,
        "bot": SELF_BOT,
        "bot_id": SELF_BOT_ID,
        "remote": REMOTE_ID,
        "remote_bot": REMOTE_BOT,
        "style": "natural_chat",
        "anti_swap": True,
        "tools": [
            "tag_peer", "ask_agent_group", "group_say", "am_i_addressed",
            "ask_agent", "peer_status", "peer_identity",
        ],
    })


async def _v1_ask_group(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400)
    prompt = (body or {}).get("prompt") or ""
    from_lab = (body or {}).get("from_lab")
    expect_lab = (body or {}).get("expect_lab")
    # If caller says who should answer, it must be us
    if expect_lab and str(expect_lab).strip().lower() != HOST_ID:
        _log("reject", reason="expect_lab", expect_lab=expect_lab)
        return JSONResponse(
            {
                "error": f"expect_lab={expect_lab} but this host is {HOST_ID}",
                "lab_id": HOST_ID,
            },
            status_code=409,
        )
    rtm = (body or {}).get("reply_to_message_id")
    try:
        rtm_i = int(rtm) if rtm is not None else None
    except Exception:
        rtm_i = None
    result = ask_agent_group(str(prompt), reply_to_message_id=rtm_i, from_lab=from_lab)
    status = 200 if not str(result).startswith("error") else 500
    return JSONResponse({"result": result, "lab_id": HOST_ID, "bot": SELF_BOT}, status_code=status)


async def _v1_group_say(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400)
    result = group_say(str((body or {}).get("text") or ""))
    status = 200 if not str(result).startswith("error") else 500
    return JSONResponse({"result": result, "lab_id": HOST_ID, "bot": SELF_BOT}, status_code=status)


async def _v1_tag_peer(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400)
    ask = (body or {}).get("ask") or (body or {}).get("prompt") or ""
    result = tag_peer(str(ask))
    status = 200 if not str(result).startswith("error") else 500
    return JSONResponse({"result": result, "lab_id": HOST_ID, "bot": SELF_BOT}, status_code=status)


def build_app():
    app = mcp.streamable_http_app()
    app.routes.insert(0, Route("/health", _health, methods=["GET"]))
    app.routes.insert(0, Route("/v1/health", _health, methods=["GET"]))
    app.routes.insert(0, Route("/v1/ask_group", _v1_ask_group, methods=["POST"]))
    app.routes.insert(0, Route("/v1/group_say", _v1_group_say, methods=["POST"]))
    app.routes.insert(0, Route("/v1/tag_peer", _v1_tag_peer, methods=["POST"]))
    app.add_middleware(BearerAuthMiddleware)
    return app


if __name__ == "__main__":
    print(
        f"[peer-hermes-mcp] host={HOST_ID} bot=@{SELF_BOT} remote={REMOTE_ID} "
        f"anti_swap=on url={REMOTE_URL}",
        file=sys.stderr,
        flush=True,
    )
    if _pair_err:
        print(_pair_err, file=sys.stderr)
        sys.exit(2)
    import uvicorn
    uvicorn.run(build_app(), host="0.0.0.0", port=PORT, log_level="warning")
