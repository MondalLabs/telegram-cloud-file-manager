"""
handlers/setup.py
─────────────────────────────────────────────────────────────────────────────
/setup command — Dump Group Auto-Detection.

The admin does NOT need to know the DUMP_CHAT_ID before deploying.

Workflow:
  1. Admin creates a private Telegram group and adds the bot as Admin.
  2. Admin sends /setup INSIDE that group.
  3. Bot captures message.chat.id (the negative integer group ID).
  4. Stores it in BotSettings collection as dump_chat_id.
  5. All subsequent CDN routing reads from BotSettings (Safeguard #1).

Security: Only the OWNER (settings.owner_id) may execute this command.
          We check this manually here rather than using @owner_only because
          the command runs in a GROUP context, not a private chat — the
          from_user is still checked, but the chat is different.
"""

from __future__ import annotations

import logging

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

from bot.client import bot
from bot.config import settings as cfg
from models.settings import BotSettings

log = logging.getLogger(__name__)


@bot.on_message(filters.command("setup") & filters.group)
async def setup_dump_group(client, message: Message) -> None:
    """Register the current group as the Storage CDN dump group."""

    # Only the owner may configure the dump group
    if message.from_user is None or message.from_user.id != cfg.owner_id:
        await message.reply("⛔ Only the bot owner can run /setup.")
        return

    chat_id: int = message.chat.id
    chat_title: str = message.chat.title or "Unknown Group"

    # Persist to DB — updates existing or creates new singleton
    bot_settings = await BotSettings.get_global()
    bot_settings.dump_chat_id = chat_id
    await bot_settings.save()

    log.info("Dump group configured: %s (%d)", chat_title, chat_id)

    await message.reply(
        f"✅ **Storage CDN Configured**\n\n"
        f"Group: **{chat_title}**\n"
        f"Chat ID: `{chat_id}`\n\n"
        f"All uploaded videos will now be routed to this group for permanent storage.\n"
        f"⚠️ **Never delete messages from this group** — they are the CDN tokens.",
        parse_mode=ParseMode.MARKDOWN,
    )
