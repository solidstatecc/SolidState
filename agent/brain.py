"""Solid State agent — conversational brain.

Replaces local Nemotron inference with Anthropic API calls.
Keeps NemoClaw on the box for sandboxed skill execution. Different jobs.

Architecture:
  Telegram → this script → Claude API
                       ↓
                       tool calls (read/write/list in /workspace)
                       ↓
                       reply back to Telegram

Run:  python -m agent.brain
"""
import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

import anthropic
import httpx


log = logging.getLogger("solidstate.brain")

# --- config ---
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
ADMIN_CHAT_ID = os.environ.get("TELEGRAM_ADMIN_CHAT_ID", "")
WORKSPACE = Path(os.environ.get("WORKSPACE_PATH", "/sandbox/.openclaw-data/workspace"))
MODEL = os.environ.get("BRAIN_MODEL", "claude-sonnet-4-6")
MAX_TURNS = int(os.environ.get("BRAIN_MAX_TURNS", "8"))
HISTORY_LIMIT = int(os.environ.get("BRAIN_HISTORY_LIMIT", "20"))

API = f"https://api.telegram.org/bot{BOT_TOKEN}"
client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

# Per-chat conversation memory. Lives in process; lost on restart.
# Move to Redis if persistence matters.
_history: dict[str, list[dict]] = {}


# --- persona loading ---


def load_persona() -> str:
    """Load voice + operating rules. Order matters — last writer wins on conflict.

    Priority (low → high):
      solidstate.md   — brand voice (marketing surface)
      AGENTS.md       — operating instructions (how the agent works)
      SOUL.md         — canonical agent voice (final word)
      voice.md        — runtime overrides
    """
    files = [
        WORKSPACE / "solidstate.md",
        WORKSPACE / "AGENTS.md",
        WORKSPACE / "SOUL.md",
        WORKSPACE / "voice.md",
    ]
    parts = [f.read_text() for f in files if f.exists()]
    if not parts:
        return _FALLBACK_PERSONA
    return "\n\n---\n\n".join(parts)


_FALLBACK_PERSONA = """You are Solid State.

Voice: contrast pairs, compression, build-from-scratch, calm leverage.

Rules:
- Median sentence 9 words. Max 18.
- Lead with the answer. Context after, only if needed.
- Single-sentence paragraphs are encouraged.
- Show the artifact. Then explain.
- One idea per line.
- Present tense, second person.
- No emojis. No buzzwords (comprehensive, leverage, synergy, seamless, delve, ecosystem, empower, unlock, robust).
- No "Would you like me to..." closings. No "In summary." No numbered option menus.
- No em-dashes as filler.
"""


# --- tools (filesystem, scoped to workspace) ---


TOOLS = [
    {
        "name": "read_file",
        "description": "Read a file from the Solid State workspace. Returns full text.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Relative path inside workspace"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write text to a file in the workspace. Overwrites.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_files",
        "description": "List files and folders at a path inside the workspace.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "default": "."}},
        },
    },
]


def _safe_path(rel: str) -> Path:
    p = (WORKSPACE / rel).resolve()
    if not str(p).startswith(str(WORKSPACE.resolve())):
        raise ValueError(f"path escapes workspace: {rel}")
    return p


async def _tool_read_file(path: str) -> str:
    p = _safe_path(path)
    if not p.exists():
        return f"NOT_FOUND: {path}"
    return p.read_text()[:50_000]


async def _tool_write_file(path: str, content: str) -> str:
    p = _safe_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"wrote {len(content)} bytes to {path}"


async def _tool_list_files(path: str = ".") -> str:
    p = _safe_path(path)
    if not p.exists():
        return f"NOT_FOUND: {path}"
    if p.is_file():
        return f"FILE: {path}"
    out = []
    for child in sorted(p.iterdir()):
        kind = "dir " if child.is_dir() else "file"
        out.append(f"{kind}  {child.name}")
    return "\n".join(out) or "(empty)"


_TOOL_FNS = {
    "read_file": _tool_read_file,
    "write_file": _tool_write_file,
    "list_files": _tool_list_files,
}


async def _exec_tool(name: str, args: dict) -> str:
    fn = _TOOL_FNS.get(name)
    if not fn:
        return f"UNKNOWN_TOOL: {name}"
    try:
        return await fn(**args)
    except Exception as e:  # noqa: BLE001
        return f"ERROR: {e}"


# --- conversation loop ---


async def reply(chat_id: str, user_text: str) -> str:
    """Run one user turn through Claude with tool use. Return final text."""
    persona = load_persona()
    history = _history.setdefault(chat_id, [])
    history.append({"role": "user", "content": user_text})
    history[:] = history[-HISTORY_LIMIT:]

    for _ in range(MAX_TURNS):
        msg = await client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=persona,
            tools=TOOLS,
            messages=history,
        )

        if msg.stop_reason == "tool_use":
            # Append assistant turn that contains the tool_use blocks
            history.append({"role": "assistant", "content": msg.content})
            tool_results = []
            for block in msg.content:
                if block.type == "tool_use":
                    output = await _exec_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": output,
                    })
            history.append({"role": "user", "content": tool_results})
            continue

        # final text response
        text = "".join(b.text for b in msg.content if b.type == "text").strip()
        history.append({"role": "assistant", "content": text})
        return text or "(empty)"

    return "(stopped after max tool turns)"


# --- telegram loop ---


async def poll_loop():
    offset = 0
    log.info("brain online — model=%s workspace=%s", MODEL, WORKSPACE)
    async with httpx.AsyncClient(timeout=35) as c:
        while True:
            try:
                r = await c.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 30})
                for upd in r.json().get("result", []):
                    offset = upd["update_id"] + 1
                    asyncio.create_task(_handle(upd, c))
            except Exception:  # noqa: BLE001
                log.exception("poll loop error; sleeping 5s")
                await asyncio.sleep(5)


async def _handle(upd: dict, c: httpx.AsyncClient) -> None:
    msg = upd.get("message")
    if not msg or "text" not in msg:
        return
    chat_id = str(msg["chat"]["id"])
    if ADMIN_CHAT_ID and chat_id != ADMIN_CHAT_ID:
        log.warning("ignoring chat %s (not admin)", chat_id)
        return

    user_text = msg["text"]
    if user_text.startswith("/reset"):
        _history.pop(chat_id, None)
        await _send(c, chat_id, "history cleared.")
        return

    await _send_typing(c, chat_id)
    try:
        out = await reply(chat_id, user_text)
    except Exception as e:  # noqa: BLE001
        log.exception("reply failed")
        out = f"error: {e}"
    await _send(c, chat_id, out)


async def _send(c: httpx.AsyncClient, chat_id: str, text: str) -> None:
    # Telegram caps at 4096 chars per message. Chunk if longer.
    for i in range(0, len(text), 4000):
        await c.post(f"{API}/sendMessage", json={"chat_id": chat_id, "text": text[i:i + 4000]})


async def _send_typing(c: httpx.AsyncClient, chat_id: str) -> None:
    try:
        await c.post(f"{API}/sendChatAction", json={"chat_id": chat_id, "action": "typing"})
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(poll_loop())
