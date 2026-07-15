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
from models.auto_delete import AutoDeleteJob


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
        document_models=[Folder, File, User, FSMState, BotSettings, AutoDeleteJob],
    )
    log.info("DB ready.")
    
    # Load live settings from MongoDB into config cache
    log.info("Loading live settings configuration...")
    db_settings = await BotSettings.get_global()
    settings.update_cache(
        protect_content=db_settings.protect_content,
        items_per_page=db_settings.items_per_page,
        bot_name=db_settings.bot_name,
        auto_delete_hours=db_settings.auto_delete_hours,
    )
    
    log.info("Synchronizing folder sizes...")
    from services.folder_service import recalculate_all_folder_sizes
    await recalculate_all_folder_sizes()
    log.info("Folder sizes synchronized.")


# ── Startup ───────────────────────────────────────────────────────────────────
_loop = asyncio.get_event_loop()

# Step 1: DB init on the current event loop
_loop.run_until_complete(_init_db())

# Step 2: Uvicorn health server on the same event loop (avoids loop conflict for Beanie)
from bot.api import router as api_router
health_app.include_router(api_router)

config = uvicorn.Config(health_app, host="0.0.0.0", port=settings.health_port, log_level="warning")
server = uvicorn.Server(config)
_loop.create_task(server.serve())
log.info("Health server starting on port %d...", settings.health_port)


async def _run():
    """Single-connection lifecycle: start → register commands → idle → stop."""
    # Step 3: Start the bot (one connection, same event loop as DB)
    await bot.start()
    log.info("Starting bot...")

    # Step 3.5: Hydrate pending auto-deletions from DB
    from services.auto_delete_service import hydrate_auto_deletions
    asyncio.create_task(hydrate_auto_deletions(bot))

    # Step 4: Register bot commands now that the client is connected
    from pyrogram.types import BotCommand
    from bot.config import settings as cfg
    _start_desc = f"📁 Open {cfg.display_name}" if cfg.display_name else "📁 Open the File Manager"
    await bot.set_bot_commands([
        BotCommand("start",  _start_desc),
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
