"""
bot/__main__.py — Entrypoint
Run with: python -m bot

Pattern: identical to the working diag_test.py.
  1. DB init on event loop (before bot starts)
  2. Uvicorn in daemon thread
  3. Register bot commands with Telegram (set_my_commands)
  4. bot.run() — NO coroutine argument (proven to work)
"""

import asyncio
import logging
import threading

import uvicorn
from pymongo import AsyncMongoClient
from beanie import init_beanie

from bot.client import bot, health_app
from bot.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("cfm")

# ── Models ────────────────────────────────────────────────────────────────────
from models.folder import Folder
from models.file import File
from models.user import User
from models.state import FSMState
from models.settings import BotSettings

# ── Handlers ──────────────────────────────────────────────────────────────────
import handlers.setup
import handlers.start
import handlers.navigation
import handlers.admin_crud
import handlers.upload
import handlers.playback
import handlers.user_mgmt
import handlers.guest

# ── Activity logger (group=99 = lowest priority, runs after all real handlers) ─
from pyrogram import filters

@bot.on_message(group=99)
async def _log_message(client, message):
    uid  = getattr(message.from_user, "id", "?")
    name = getattr(message.from_user, "first_name", "?")
    text = message.text or f"<{message.media}>"
    log.info("MSG  ← [%s | %s] %s", uid, name, text)

@bot.on_callback_query(group=99)
async def _log_callback(client, query):
    uid  = getattr(query.from_user, "id", "?")
    name = getattr(query.from_user, "first_name", "?")
    log.info("CB   ← [%s | %s] %s", uid, name, query.data)


async def _init_db():
    log.info("Connecting to MongoDB Atlas...")
    mongo_client = AsyncMongoClient(settings.mongo_uri)
    await init_beanie(
        database=mongo_client[settings.db_name],
        document_models=[Folder, File, User, FSMState, BotSettings],
    )
    log.info("DB ready.")


# ── Startup ───────────────────────────────────────────────────────────────────
_loop = asyncio.get_event_loop()

# Step 1: DB init on the current event loop
_loop.run_until_complete(_init_db())

# Step 2: Uvicorn health server in a daemon thread (separate loop, no conflict)
threading.Thread(
    target=lambda: uvicorn.run(health_app, host="0.0.0.0", port=settings.health_port, log_level="warning"),
    daemon=True,
    name="uvicorn",
).start()
log.info("Health server starting on port %d...", settings.health_port)


async def _run():
    """Single-connection lifecycle: start → register commands → idle → stop."""
    # Step 3: Start the bot (one connection, same event loop as DB)
    await bot.start()
    log.info("Starting bot...")

    # Step 4: Register bot commands now that the client is connected
    from pyrogram.types import BotCommand
    await bot.set_bot_commands([
        BotCommand("start",  "📁 Open the Cloud File Manager"),
        BotCommand("done",   "✅ Finish current upload session"),
        BotCommand("cancel", "❌ Cancel current operation"),
    ])
    log.info("Bot commands registered with Telegram.")
    log.info("Bot ready. Waiting for messages...")

    # Step 5: Idle — sleep in chunks so KeyboardInterrupt is caught cleanly
    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        log.info("Shutting down...")
        await bot.stop()


try:
    _loop.run_until_complete(_run())
except KeyboardInterrupt:
    pass
