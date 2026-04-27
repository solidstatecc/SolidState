"""Telegram admin protocol.

You are the editor-in-chief. The agent is the staff.
Bot listens for commands from the admin chat. Replies with status.
"""
import asyncio
import logging
import os
from typing import Optional

import httpx


log = logging.getLogger("solidstate.telegram")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ADMIN_CHAT_ID = os.environ.get("TELEGRAM_ADMIN_CHAT_ID", "")
API = f"https://api.telegram.org/bot{BOT_TOKEN}"


async def notify_admin(text: str) -> None:
    """Push a message to the admin chat. Silent failure — never break a run."""
    if not BOT_TOKEN or not ADMIN_CHAT_ID:
        log.warning("telegram not configured; skipping notify: %s", text[:80])
        return
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            await c.post(
                f"{API}/sendMessage",
                json={"chat_id": ADMIN_CHAT_ID, "text": text, "parse_mode": "Markdown"},
            )
    except Exception:  # noqa: BLE001
        log.exception("telegram notify failed")


# ---------- long-poll loop (run as a separate process) ----------


COMMANDS = {
    "/status": "show_status",
    "/approve": "approve_skill",
    "/reject": "reject_skill",
    "/featured": "set_featured",
    "/payouts": "show_payouts",
    "/help": "show_help",
}


HELP = """*Solid State admin*
/status — service health + queue depth
/approve <skill_id> — publish a pending skill
/reject <skill_id> <reason> — reject a pending skill
/featured <skill_id> — feature on the homepage
/payouts — pending seller payouts
"""


async def poll_loop():
    """Long-poll Telegram for admin commands. Run via a worker process."""
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set")
    offset = 0
    async with httpx.AsyncClient(timeout=35) as c:
        while True:
            try:
                r = await c.get(
                    f"{API}/getUpdates",
                    params={"offset": offset, "timeout": 30},
                )
                for update in r.json().get("result", []):
                    offset = update["update_id"] + 1
                    await _handle(update, c)
            except Exception:  # noqa: BLE001
                log.exception("poll loop error; backing off")
                await asyncio.sleep(5)


async def _handle(update: dict, client: httpx.AsyncClient) -> None:
    msg = update.get("message")
    if not msg:
        return
    chat_id = str(msg["chat"]["id"])
    if ADMIN_CHAT_ID and chat_id != ADMIN_CHAT_ID:
        return  # ignore non-admins
    text = (msg.get("text") or "").strip()
    if not text.startswith("/"):
        return

    parts = text.split()
    cmd = parts[0].split("@")[0]
    args = parts[1:]
    handler = _HANDLERS.get(cmd)
    if not handler:
        await _reply(client, chat_id, "unknown command. /help")
        return
    reply = await handler(args)
    await _reply(client, chat_id, reply)


async def _reply(client: httpx.AsyncClient, chat_id: str, text: str) -> None:
    await client.post(
        f"{API}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
    )


# ---------- command handlers ----------


async def _show_help(_args):
    return HELP


async def _show_status(_args):
    from ..db.supabase import queue_depth, recent_runs
    depth = await queue_depth()
    last = await recent_runs(limit=5)
    lines = [f"*queue:* {depth}", "", "*recent runs:*"]
    for r in last:
        lines.append(f"`{r['id'][:8]}` {r['skill_id']} — {r['status']}")
    return "\n".join(lines)


async def _approve(args):
    from ..db.supabase import set_skill_status
    if not args:
        return "usage: /approve <skill_id>"
    await set_skill_status(args[0], "published")
    return f"approved {args[0]}"


async def _reject(args):
    from ..db.supabase import set_skill_status
    if len(args) < 2:
        return "usage: /reject <skill_id> <reason>"
    skill_id = args[0]
    reason = " ".join(args[1:])
    await set_skill_status(skill_id, "rejected", reason=reason)
    return f"rejected {skill_id}: {reason}"


async def _featured(args):
    from ..db.supabase import set_featured
    if not args:
        return "usage: /featured <skill_id>"
    await set_featured(args[0])
    return f"featured {args[0]}"


async def _payouts(_args):
    from ..db.supabase import pending_payouts
    rows = await pending_payouts()
    if not rows:
        return "no pending payouts"
    lines = ["*pending payouts:*"]
    for r in rows:
        lines.append(f"`{r['seller_id'][:8]}` ${r['amount_usd']:.2f}")
    return "\n".join(lines)


_HANDLERS = {
    "/help": _show_help,
    "/status": _show_status,
    "/approve": _approve,
    "/reject": _reject,
    "/featured": _featured,
    "/payouts": _payouts,
}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(poll_loop())
