"""
bot/client.py
─────────────────────────────────────────────────────────────────────────────
Pyrofork MTProto client singleton + FastAPI health server.

Both objects are created here and imported everywhere else — this guarantees
a single shared connection pool and a single Telegram session throughout the
entire process lifetime.
"""

from pyrogram import Client
from fastapi import FastAPI

from bot.config import settings

# ── Pyrofork MTProto client ───────────────────────────────────────────────────
# Pinning the session to an explicit path ensures the .session file is ALWAYS
# written to the project root, regardless of which directory the process is
# launched from. This prevents stale duplicate sessions appearing in /bot/.
import os as _os
_SESSION = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "cfm_bot")

bot = Client(
    name=_SESSION,
    api_id=settings.api_id,
    api_hash=settings.api_hash,
    bot_token=settings.bot_token,
)


# ── FastAPI health server ─────────────────────────────────────────────────────
# Render Web Service requires the process to bind a port; this lightweight
# server satisfies that requirement and gives UptimeRobot a ping target.
health_app = FastAPI(title="Health Server")


@health_app.get("/health")
async def health_check() -> dict:
    """Uptime ping endpoint — called every 5 min by UptimeRobot."""
    return {"status": "ok", "service": "cloud-file-manager"}


@health_app.get("/")
async def root() -> dict:
    return {"status": "ok"}
