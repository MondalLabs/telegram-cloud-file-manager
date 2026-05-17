"""
handlers/playback.py
─────────────────────────────────────────────────────────────────────────────
Frictionless video delivery — single-click playback for approved users.

Callback pattern: play:{file_doc_id}

Flow:
  1. User clicks 🎬 video button in the listing.
  2. Bot fetches the File document from MongoDB (just the file_id token).
  3. Bot calls send_video(chat_id, video=file.file_id).
     • This is a server-side token reference — Telegram streams the video
       from its CDN directly to the user.
     • The bot process touches ZERO bytes of the video payload.
     • The user sees native inline streaming in the Telegram player.
  4. callback_query.answer() dismisses the loading spinner.

The file_id used here is the one obtained from the dump group via
copy_message() during upload — it is the permanent CDN token for the
dump group copy, which the bot can reuse indefinitely.
"""

from __future__ import annotations

import logging

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import CallbackQuery
from beanie import PydanticObjectId

from bot.client import bot
from models.user import User
from middlewares.access_control import approved_and_above
import services.file_service as file_service
from utils.callback_data import decode

log = logging.getLogger(__name__)


@bot.on_callback_query(filters.regex(r"^play:"))
@approved_and_above
async def play_video(client, query: CallbackQuery, user: User) -> None:
    """
    Deliver a video to the user via its permanent Telegram file_id token.

    Safeguard #1 compliance: send_video(video=file_id) is a server-side
    reference — no download, no RAM consumption, pure CDN streaming.
    """
    # Dismiss the button loading spinner immediately
    await query.answer("🎬 Loading…")

    parts = decode(query.data)
    if len(parts) < 2:
        await query.answer("❌ Invalid request.", show_alert=True)
        return

    file_doc_id = parts[1]
    try:
        file_doc = await file_service.get_file(PydanticObjectId(file_doc_id))
    except Exception:
        await query.answer("❌ Invalid file ID.", show_alert=True)
        return

    if file_doc is None:
        await query.answer("❌ File not found — it may have been deleted.", show_alert=True)
        return

    # Build a rich caption with metadata
    caption_parts = [f"🎬 **{file_doc.name}**"]
    if file_doc.duration is not None:
        m, s = divmod(file_doc.duration, 60)
        caption_parts.append(f"⏱ {m}m {s:02d}s" if m else f"⏱ {s}s")
    if file_doc.width and file_doc.height:
        caption_parts.append(f"📐 {file_doc.width}×{file_doc.height}")
    if file_doc.file_size:
        mb = file_doc.file_size / (1024 * 1024)
        caption_parts.append(f"💾 {mb:.1f} MB")

    caption = "  ·  ".join(caption_parts)

    try:
        if file_doc.file_type == "video":
            await client.send_video(
                chat_id=query.from_user.id,
                video=file_doc.file_id,
                caption=caption,
                parse_mode=ParseMode.MARKDOWN,
                supports_streaming=True,
            )
        else:
            # document — forward as file with rich caption
            await client.send_document(
                chat_id=query.from_user.id,
                document=file_doc.file_id,
                caption=caption,
                parse_mode=ParseMode.MARKDOWN,
            )
        log.info(
            "Delivered file %s (%s) to user %d",
            file_doc.name, file_doc.file_id[:12] + "…", user.telegram_id,
        )
    except Exception as e:
        log.error("Playback error for file %s: %s", file_doc_id, e, exc_info=True)
        # file_id may have expired — rare but possible
        await client.send_message(
            chat_id=query.from_user.id,
            text=(
                f"❌ **Playback Error**\n\n"
                f"Could not deliver **{file_doc.name}**.\n"
                f"The CDN token may have expired. Please contact the administrator."
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
