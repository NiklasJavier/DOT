"""Pure peer chat model: address detection, natural shapes, identity invariants."""
from __future__ import annotations

import os
import re
from typing import Iterable

# Operating Protocol version this model implements
# (skills/lab-peer-chat/references/protocol.md in ErynoaGroup/.ai-harness).
PROTOCOL_VERSION = "1.0.0"

HOME_CHAT_ID = "-5535276728"

_PEER_DEFAULTS: dict[str, dict[str, str]] = {
    "alpha": {
        "mark": "α",
        "name": "alpha",
        "bot": "erynoa_alpha_hermes_bot",
        "bot_id": "8817307555",
        "remote_url": "http://lab-beta:8755",
        "remote_id": "beta",
        "remote_mark": "β",
        "remote_name": "beta",
        "remote_bot": "erynoa_beta_hermes_bot",
        "remote_bot_id": "8734599900",
    },
    "beta": {
        "mark": "β",
        "name": "beta",
        "bot": "erynoa_beta_hermes_bot",
        "bot_id": "8734599900",
        "remote_url": "http://lab-alpha:8755",
        "remote_id": "alpha",
        "remote_mark": "α",
        "remote_name": "alpha",
        "remote_bot": "erynoa_alpha_hermes_bot",
        "remote_bot_id": "8817307555",
    },
}

PEER_MAP = _PEER_DEFAULTS

_ALIASES: dict[str, tuple[str, ...]] = {
    "alpha": (
        "alpha", "alfa", "α",
        "erynoa_alpha_hermes_bot", "@erynoa_alpha_hermes_bot",
    ),
    "beta": (
        "beta", "berta", "β",
        "erynoa_beta_hermes_bot", "@erynoa_beta_hermes_bot",
    ),
}


def resolve_me(host_id: str, remote_url_override: str | None = None) -> dict[str, str]:
    host_id = (host_id or "").strip().lower()
    base = dict(
        _PEER_DEFAULTS.get(
            host_id,
            {
                "mark": (host_id[:1] or "?"),
                "name": host_id or "lab",
                "bot": f"erynoa_{host_id}_hermes_bot",
                "bot_id": "",
                "remote_url": "",
                "remote_id": "peer",
                "remote_mark": "?",
                "remote_name": "peer",
                "remote_bot": "",
                "remote_bot_id": "",
            },
        )
    )
    if remote_url_override is not None:
        override = remote_url_override.strip()
    else:
        running = (os.environ.get("LAB_ID") or os.environ.get("PEER_MCP_HOST_ID") or "").strip().lower()
        override = os.environ.get("PEER_REMOTE_URL", "").strip() if running == host_id else ""
    if override:
        base["remote_url"] = override
    return base


def assert_peer_pair(host_id: str, remote_id: str) -> str | None:
    """Return error if host/remote pair is invalid or swapped."""
    h = (host_id or "").strip().lower()
    r = (remote_id or "").strip().lower()
    if not h or h not in _PEER_DEFAULTS:
        return f"error: unknown host lab_id={host_id!r}"
    if not r or r not in _PEER_DEFAULTS:
        return f"error: unknown remote lab_id={remote_id!r}"
    if h == r:
        return f"error: host and remote must differ (got {h})"
    expected = _PEER_DEFAULTS[h]["remote_id"]
    if r != expected:
        return f"error: lab {h} must talk to {expected}, not {r}"
    # reverse must point back
    if _PEER_DEFAULTS[r]["remote_id"] != h:
        return f"error: peer map not symmetric for {h}<->{r}"
    return None


def assert_bot_matches_lab(lab_id: str, telegram_username: str) -> str | None:
    """Return error if Telegram getMe username is not this lab's bot."""
    lab = (lab_id or "").strip().lower()
    uname = (telegram_username or "").strip().lstrip("@").lower()
    if lab not in _PEER_DEFAULTS:
        return f"error: unknown lab {lab_id!r}"
    expected = _PEER_DEFAULTS[lab]["bot"].lower()
    if uname != expected:
        return (
            f"error: identity mismatch — lab={lab} must post as @{expected}, "
            f"token is @{uname or '?'} (refusing post to prevent swapped answers)"
        )
    return None


def assert_remote_health(host_id: str, remote_health_lab_id: str) -> str | None:
    """Remote /v1/health lab_id must be the expected peer, never self."""
    h = (host_id or "").strip().lower()
    rid = (remote_health_lab_id or "").strip().lower()
    if not rid:
        return "error: remote health missing lab_id"
    if rid == h:
        return f"error: remote URL points to self ({h}) — would swap speakers"
    err = assert_peer_pair(h, rid)
    if err:
        return err
    return None


def _norm(text: str) -> str:
    return " ".join(str(text or "").lower().split())


def _contains_token(text_norm: str, token: str) -> bool:
    t = token.lower().lstrip("@")
    if not t:
        return False
    if t.startswith("erynoa_") or "bot" in t:
        return t in text_norm or f"@{t}" in text_norm
    return re.search(rf"(?<!\w){re.escape(t)}(?!\w)", text_norm) is not None


def is_addressed_to(
    text: str,
    lab_id: str,
    *,
    reply_to_is_self: bool = False,
    explicit_mentions: Iterable[str] | None = None,
) -> bool:
    lab = (lab_id or "").strip().lower()
    if not lab:
        return False
    if reply_to_is_self:
        return True
    aliases = _ALIASES.get(lab, (lab, f"erynoa_{lab}_hermes_bot"))
    text_n = _norm(text)
    for a in aliases:
        if _contains_token(text_n, a):
            return True
    if explicit_mentions:
        me_bot = resolve_me(lab).get("bot", "").lower()
        for m in explicit_mentions:
            ml = str(m).lower().lstrip("@")
            if ml == me_bot or ml == lab:
                return True
    return False


def is_addressed_to_peer(text: str, lab_id: str) -> bool:
    me = resolve_me(lab_id)
    peer = me.get("remote_id") or ""
    return is_addressed_to(text, peer)


def _bot_handles(mentions: Iterable[str] | None) -> set[str]:
    out: set[str] = set()
    for m in mentions or ():
        h = str(m).strip().lstrip("@").lower()
        if h.startswith("erynoa_") and h.endswith("_hermes_bot"):
            out.add(h)
    return out


def should_alpha_free_respond(
    text: str,
    mentions: Iterable[str] | None = None,
    *,
    reply_to_bot: str | None = None,
    chat_id: str = HOME_CHAT_ID,
    free_response_chats: Iterable[str] = (HOME_CHAT_ID,),
    author_is_human: bool = True,
    lab_id: str = "alpha",
) -> bool:
    """Protocol §4: the leader free-responds iff the chat is a free-response
    chat, the author is human, the turn is not exclusively another bot's
    mention (T3) and not a reply to another bot (T6).

    Deliberately ignores names in `text`: prose never addresses a bot —
    only Telegram entities (mentions / reply-to) do (protocol §3).
    """
    if not author_is_human:
        return False
    if str(chat_id) not in {str(c) for c in free_response_chats}:
        return False
    me_bot = resolve_me(lab_id).get("bot", "").lower()
    if reply_to_bot:
        rb = str(reply_to_bot).strip().lstrip("@").lower()
        if rb and rb != me_bot:
            return False  # T6 — that turn belongs to the replied-to bot
    bots = _bot_handles(mentions)
    if bots and me_bot not in bots:
        return False  # T3 — exclusively other bot(s) mentioned
    return True


def parse_message_id(post_result: str) -> int | None:
    """Extract message_id from a `_telegram_post` result line."""
    if "message_id=" not in (post_result or ""):
        return None
    try:
        return int(post_result.split("message_id=")[1].split()[0].strip())
    except Exception:
        return None


def monotonic_warning(self_mid: int | None, peer_mid: int | None) -> str | None:
    """Peer's reply must be posted after the caller's line (protocol §6)."""
    if self_mid and peer_mid and peer_mid <= self_mid:
        return f"warning: peer_message_id={peer_mid} <= self_message_id={self_mid}"
    return None


def clean_chat_text(text: str, max_len: int = 900) -> str:
    """Strip machine/lab labels so group text looks like a normal chat message."""
    s = str(text or "").strip()
    # drop PEER frames first
    s = re.sub(r"\bPEER\s+[αβa-zA-Z?]+\s*→\s*[αβa-zA-Z?]+\s*:\s*", "", s, flags=re.I)
    s = re.sub(r"\bPEER\s+[αβa-zA-Z?]+\s*->\s*[αβa-zA-Z?]+\s*:\s*", "", s, flags=re.I)
    # drop @bot handles (display name is already the Telegram sender)
    s = re.sub(r"@?erynoa_\w+_hermes_bot\b\s*", "", s, flags=re.I)
    # drop leading lab marks / name labels: "α:", "β:", "alpha:", "Beta —", "[alpha]", etc.
    for _ in range(3):  # nested junk
        s2 = re.sub(
            r"^(?:[αβ]|alpha|beta|alfa|berta)\s*[:：\-—–|]\s*",
            "",
            s,
            flags=re.I,
        )
        s2 = re.sub(r"^\[(?:alpha|beta|α|β)\]\s*", "", s2, flags=re.I)
        s2 = re.sub(r"^(?:lab\s+)?(?:alpha|beta)\s+", "", s2, flags=re.I)
        if s2 == s:
            break
        s = s2.strip()
    s = " ".join(s.split())
    if len(s) > max_len:
        s = s[: max_len - 1] + "…"
    return s


def format_chat_outbound(ask: str, *, peer_bot: str, peer_name: str) -> str:
    body = clean_chat_text(ask, max_len=700)
    if not body:
        body = "…"
    pb = (peer_bot or "").lstrip("@")
    if pb and f"@{pb}".lower() not in body.lower():
        return f"@{pb} {body}"
    return body


def format_chat_reply(reply: str) -> str:
    """Final text posted to Telegram — plain chat, no lab badges."""
    body = clean_chat_text(reply, max_len=1200)
    for bad in ("skill_view", "mcp__", "Reading skill", "ask_agent", "PEER "):
        if bad in body:
            body = "\n".join(ln for ln in body.splitlines() if bad not in ln).strip()
    # never allow starting with greek/lab mark after clean
    body = re.sub(r"^[αβ]\s*", "", body)
    return body or "…"


def is_fast_ping(ask: str) -> bool:
    s = clean_chat_text(ask).lower().strip(" ?.!")
    pings = {
        "ping", "pong", "online", "online?", "da", "da?", "hi", "hey", "hallo",
        "hello", "status", "up", "alive", "ack", "ok", "hier", "hier?",
        "bist du da", "bist du online", "noch da", "melder", "melde dich",
    }
    if s in pings:
        return True
    if len(s) <= 24 and any(s.startswith(p) for p in ("ping", "online", "da?", "hi ", "hey")):
        return True
    return False


def fast_pong_text(lab_id: str) -> str:
    # Natural chat — no alpha/beta label; Telegram already shows who spoke
    return "Ja, bin online."


def format_peer_ask_line(ask: str, *, mark: str, remote_mark: str, remote_bot: str) -> str:
    peer_name = "beta" if "beta" in (remote_bot or "") else "alpha"
    return format_chat_outbound(ask, peer_bot=remote_bot, peer_name=peer_name)


def format_peer_reply_line(reply: str, *, mark: str, address_bot: str = "") -> str:
    return format_chat_reply(reply)


def validate_nonempty(value: str, label: str = "text") -> str | None:
    if not value or not str(value).strip():
        return f"error: empty {label}"
    return None
