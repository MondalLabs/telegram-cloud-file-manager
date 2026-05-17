"""
handlers/upload.py
─────────────────────────────────────────────────────────────────────────────
Bulk video upload pipeline (Owner only).

FSM state: "upload:waiting_files"
  data: {folder_id, count, folder_display_name}

Flow:
  1. Admin clicks 📤 Upload → bot enters upload:waiting_files state.
  2. Admin sends video/document files one by one (or in bulk via drag-drop).
  3. For EACH file:
     a) Detect media: message.video or message.document  (Safeguard #4)
     b) copy_message() to dump group — zero RAM          (Safeguard #1)
     c) Auto-extract all metadata via getattr()          (Safeguard #4)
     d) Index into MongoDB as a File document.
     e) Reply ✅ Indexed: {filename} ({meta})
  4. Admin sends /done (or taps ✅ Done button) → clear state → summary.

Callback: upl:{folder_id}  — starts the upload session.
Command:  /done             — finalises the session.
Callback: upload_done       — same as /done from the keyboard button.

The bot handler only processes media messages when the user is in the
"upload:waiting_files" state, so it doesn't accidentally intercept
files sent in other contexts.
"""

from __future__ import annotations

import asyncio
import logging

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message, CallbackQuery
from beanie import PydanticObjectId

from bot.client import bot
from models.user import User, UserRole
from middlewares.access_control import owner_only
from keyboards.admin_kb import upload_cancel_kb, admin_dashboard_kb
import services.folder_service as folder_service
import services.file_service as file_service
import services.fsm_service as fsm_service
from utils.callback_data import decode, ACTION_UPL

log = logging.getLogger(__name__)


# ── Start upload session ──────────────────────────────────────────────────────

@bot.on_callback_query(filters.regex(r"^upl:"))
@owner_only
async def upload_start(client, query: CallbackQuery, user: User) -> None:
    """Enter upload mode for the specified folder."""
    await query.answer()
    parts = decode(query.data)
    folder_id = parts[1]  # "root" or ObjectId string

    # Resolve folder display name for the UI prompt
    if folder_id == "root":
        display_name = "Root"
        folder_id_stored = "root"
    else:
        folder = await folder_service.get_folder(PydanticObjectId(folder_id))
        if folder is None:
            await query.edit_message_text("❌ Folder not found.")
            return
        display_name = folder.name
        folder_id_stored = folder_id

    await fsm_service.set_state(
        user.telegram_id,
        state="upload:waiting_files",
        data={"folder_id": folder_id_stored, "count": 0, "folder_name": display_name},
    )

    await query.edit_message_text(
        f"📤 **Upload Mode Active**\n\n"
        f"Uploading to: 📁 **{display_name}**\n\n"
        f"Send your video files now. I'll index each one as it arrives.\n"
        f"Send /done or tap the button below when finished.",
        reply_markup=upload_cancel_kb(),
        parse_mode=ParseMode.MARKDOWN,
    )


# ── Per-file handler (fires when user is in upload state) ─────────────────────

@bot.on_message(filters.private & (filters.video | filters.document))
@owner_only
async def upload_file_handler(client, message: Message, user: User) -> None:
    """
    Process each incoming video/document during an active upload session.

    Only acts when FSM state is "upload:waiting_files".
    Silently ignores files sent outside of an upload session.
    """
    state, data = await fsm_service.get_state_and_data(user.telegram_id)
    if state != "upload:waiting_files":
        return  # Not in upload mode — ignore

    folder_id_str: str = data.get("folder_id", "root")
    folder_id_obj: PydanticObjectId | None = (
        PydanticObjectId(folder_id_str) if folder_id_str != "root" else None
    )

    # Send a "processing" indicator
    processing_msg = await message.reply("⏳ Processing…")

    try:
        # route_to_cdn implements Safeguard #1 (copy_message) and #4 (video/doc detection)
        file_doc = await file_service.route_to_cdn(
            client=client,
            message=message,
            folder_id=folder_id_obj,
            uploaded_by=user.telegram_id,
        )

        # Increment count in FSM data
        new_count = data.get("count", 0) + 1
        await fsm_service.update_data(user.telegram_id, count=new_count)

        await processing_msg.edit_text(
            f"✅ **Indexed** ({new_count})\n"
            f"📄 {file_doc.name}\n"
            f"_{file_doc.display_meta}_",
            parse_mode=ParseMode.MARKDOWN,
        )

    except RuntimeError as e:
        # Dump group not configured
        await processing_msg.edit_text(
            f"❌ **Error:** {e}\n\n"
            f"Please run /setup in your dump group first.",
        )
        await fsm_service.clear_state(user.telegram_id)

    except Exception as e:
        log.error("Upload pipeline error: %s", e, exc_info=True)
        await processing_msg.edit_text(f"❌ Failed to index this file: {e}")


# ── /done command ─────────────────────────────────────────────────────────────

@bot.on_message(filters.command("done") & filters.private)
@owner_only
async def upload_done_command(client, message: Message, user: User) -> None:
    """Finalize the upload session."""
    await _finalize_upload(client, message, user)


@bot.on_callback_query(filters.regex(r"^upload_done$"))
@owner_only
async def upload_done_callback(client, query: CallbackQuery, user: User) -> None:
    """Finalize the upload session from the keyboard button."""
    await query.answer()
    await _finalize_upload(client, query, user)


async def _finalize_upload(client, update: Message | CallbackQuery, user: User) -> None:
    """Shared finalisation logic for /done and the ✅ Done button."""
    state, data = await fsm_service.get_state_and_data(user.telegram_id)

    if state != "upload:waiting_files":
        if isinstance(update, CallbackQuery):
            await update.edit_message_text(
                "ℹ️ No active upload session.", reply_markup=admin_dashboard_kb()
            )
        else:
            await update.reply("ℹ️ No active upload session.")
        return

    count = data.get("count", 0)
    folder_name = data.get("folder_name", "Root")
    folder_id = data.get("folder_id", "root")

    await fsm_service.clear_state(user.telegram_id)

    summary = (
        f"✅ **Upload Complete**\n\n"
        f"📁 Folder: **{folder_name}**\n"
        f"🎬 Files indexed: **{count}**\n\n"
        f"Refreshing folder view…"
    )

    if isinstance(update, CallbackQuery):
        await update.edit_message_text(summary, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.reply(summary, parse_mode=ParseMode.MARKDOWN)

    # Small delay then refresh navigation
    await asyncio.sleep(1)
    from handlers.navigation import render_folder

    # render_folder handles both Message and CallbackQuery natively
    await render_folder(
        client,
        update,
        folder_id=folder_id,
        page=1,
        user=user,
    )
