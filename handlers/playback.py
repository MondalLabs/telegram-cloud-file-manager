"""
handlers/playback.py
─────────────────────────────────────────────────────────────────────────────
Frictionless file delivery — single-click for approved users.

Callback pattern: play:{file_doc_id}

Flow:
  1. User clicks file button in the listing.
  2. Bot fetches the File document from MongoDB (just the file_id token).
  3. Bot sends the file via its permanent CDN file_id — zero bytes downloaded.
  4. File auto-deletes from the chat after 4 hours.
  5. Nav menu re-appears below the file so it stays at the bottom.
"""

from __future__ import annotations
from utils.sanitize import escape_markdown

import asyncio
import logging

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import CallbackQuery
from beanie import PydanticObjectId

from bot.client import bot
from bot.config import settings as cfg
from models.user import User
from middlewares.access_control import approved_and_above
import services.file_service as file_service
import services.folder_service as folder_service
import services.user_service as user_service
from utils.callback_data import decode
from services.auto_delete_service import schedule_auto_delete

log = logging.getLogger(__name__)

def _delete_label() -> str:
    """Human-readable auto-delete time string, built from the live cfg value."""
    seconds = cfg.auto_delete_hours * 3600
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    h = cfg.auto_delete_hours
    return f"{h:g} hour{'s' if h != 1 else ''}"

# ── Helpers ───────────────────────────────────────────────────────────────────


class _SendAdapter:
    """Lets render_folder send a NEW message instead of editing an existing one."""
    def __init__(self, client, chat_id: int):
        self._client = client
        self._chat_id = chat_id

    async def reply(self, text: str, **kwargs) -> None:
        await self._client.send_message(self._chat_id, text, **kwargs)

async def _build_caption(file_doc, client=None) -> str:
    """Build a clean, organized caption with folder path and metadata."""
    # ── Folder breadcrumb path ──────────────────────────────────────────────

    if file_doc.folder_id:
        crumbs = await folder_service.get_breadcrumbs(file_doc.folder_id)
        parts = ["🏠 Root"] + [f"📁 {escape_markdown(c.name)}" for c in crumbs]
        folder_path = "  ›  ".join(parts)
    else:
        folder_path = "🏠 Root"

    # ── Metadata line ───────────────────────────────────────────────────────
    meta: list[str] = []
    if file_doc.duration is not None:
        m, s = divmod(file_doc.duration, 60)
        meta.append(f"⏱ {m}m {s:02d}s" if m else f"⏱ {s}s")
    if file_doc.width and file_doc.height:
        meta.append(f"📐 {file_doc.width}×{file_doc.height}")
    if file_doc.file_size:
        if file_doc.file_size >= 1024 * 1024 * 1024:
            gb = file_doc.file_size / (1024 * 1024 * 1024)
            meta.append(f"💾 {gb:.2f} GB")
        else:
            mb = file_doc.file_size / (1024 * 1024)
            meta.append(f"💾 {mb:.1f} MB")

    meta_line = "  ·  ".join(meta) if meta else ""

    # ── Assemble caption ────────────────────────────────────────────────────
    lines = [
        f"📂 {folder_path}",
        "",
        f"{file_doc.icon} **{escape_markdown(file_doc.name)}**",
    ]
    if meta_line:
        lines.append(meta_line)
    lines += [
        "",
    ]
    # Only add the auto-delete warning if the feature is enabled
    if cfg.auto_delete_hours > 0:
        lines += [
            f"⚠️ __Auto-deletes from this chat in {_delete_label()}.__",
            "__Request again if you need it later.__",
        ]
    return "\n".join(lines)

# ── Main handler ──────────────────────────────────────────────────────────────

@bot.on_callback_query(filters.regex(r"^play:"))
@approved_and_above
async def play_video(client, query: CallbackQuery, user: User) -> None:
    """
    Deliver a file to the user via its permanent Telegram file_id token.
    Safeguard #1: send_*() with file_id is a server-side CDN reference —
    zero download, zero RAM consumption.
    """
    await query.answer("⏳ Preparing file…")

    parts = decode(query.data)
    if len(parts) < 2:
        await query.answer("❌ Invalid request.", show_alert=True)
        return

    file_doc_id = parts[1]

    if not PydanticObjectId.is_valid(file_doc_id):
        await query.answer("❌ Invalid file ID.", show_alert=True)
        return

    file_doc = await file_service.get_file(PydanticObjectId(file_doc_id))

    if file_doc is None:
        await query.answer("❌ File not found — it may have been deleted.", show_alert=True)
        return

    # Check permission exception
    if not await user_service.has_file_access(user, file_doc.folder_id):
        await query.answer("🔒 Access Denied: Restricted folder.", show_alert=True)
        return

    chat_id = query.from_user.id
    caption = await _build_caption(file_doc)

    try:
        # ── Send the file (zero-copy CDN reference) ─────────────────────────
        if file_doc.file_type == "video":
            sent = await client.send_video(
                chat_id=chat_id,
                video=file_doc.file_id,
                caption=caption,
                parse_mode=ParseMode.MARKDOWN,
                supports_streaming=True,
                protect_content=cfg.protect_content,
            )
        elif file_doc.file_type == "photo":
            sent = await client.send_photo(
                chat_id=chat_id,
                photo=file_doc.file_id,
                caption=caption,
                parse_mode=ParseMode.MARKDOWN,
                protect_content=cfg.protect_content,
            )
        else:
            # document, pdf, etc.
            sent = await client.send_document(
                chat_id=chat_id,
                document=file_doc.file_id,
                caption=caption,
                parse_mode=ParseMode.MARKDOWN,
                protect_content=cfg.protect_content,
            )

        log.info(
            "Delivered file %s (%s…) to user %d",
            file_doc.name, file_doc.file_id[:12], user.telegram_id,
        )

        # ── Auto-delete the file after configured hours (0 = disabled) ─────────
        if cfg.auto_delete_hours > 0:
            await schedule_auto_delete(client, chat_id, sent.id, cfg.auto_delete_hours)

        # ── Bring nav menu back to the bottom ───────────────────────────────
        # Delete the old nav message (it's now above the file), then re-send
        # it below so the user always sees the menu at the bottom of the chat.
        old_nav_id = query.message.id
        folder_id_str = str(file_doc.folder_id) if file_doc.folder_id else "root"

        await asyncio.sleep(0.5)  # Small pause for natural feel

        try:
            await client.delete_messages(chat_id, old_nav_id)
        except Exception:
            pass  # Nav may already be gone

        from handlers.navigation import render_folder
        await render_folder(
            client,
            _SendAdapter(client, chat_id),
            folder_id=folder_id_str,
            page=1,
            user=user,
        )

    except Exception as e:
        log.error("Playback error for file %s: %s", file_doc_id, e, exc_info=True)
        await client.send_message(
            chat_id=chat_id,
            text=(
                f"❌ **Playback Error**\n\n"
                f"Could not deliver **{escape_markdown(file_doc.name)}**.\n"
                f"The CDN token may have expired. Please contact the administrator."
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
