"""
handlers/navigation.py
─────────────────────────────────────────────────────────────────────────────
Directory browsing — the primary read interface for all non-guest users.

Callback patterns handled:
  nav:{folder_id}:{page}   — browse into a folder (folder_id="root" for root)
  back:{parent_id}         — navigate to parent folder
  noop                     — the page-indicator button (does nothing)

render_folder() is the shared core function also called from:
  • handlers/start.py        (home callback)
  • handlers/admin_crud.py   (after CRUD operations to refresh the view)
  • handlers/upload.py        (after upload session completes)

Breadcrumb format in the header message:
  🏠 Root  ›  📁 Semester 1  ›  📁 Civil  ›  📁 Hydraulics
"""

from __future__ import annotations
from utils.sanitize import escape_markdown

import logging
import asyncio
from typing import Optional

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message, CallbackQuery

from bot.client import bot
from models.user import User, UserRole
from middlewares.access_control import approved_and_above, owner_only
from keyboards.navigation_kb import build_folder_keyboard, build_empty_folder_keyboard
from keyboards.admin_kb import folder_actions_kb, file_actions_kb
import services.folder_service as folder_service
import services.file_service as file_service
from utils.callback_data import (
    decode,
    encode,
    ACTION_NAV,
    ACTION_BACK,
    ACTION_FOLDER_INFO,
    ACTION_FILE_INFO,
)
from beanie import PydanticObjectId

log = logging.getLogger(__name__)

# ── Core shared render function ───────────────────────────────────────────────


async def render_folder(
    client,
    update: Message | CallbackQuery,
    folder_id: Optional[str],  # None or "root" → root level
    page: int,
    user: User,
) -> None:
    """
    Fetch folder contents and render (or edit) the navigation keyboard.
    Called from multiple handlers — this is the single source of truth
    for building the directory listing UI.
    """
    is_admin = user.role == UserRole.OWNER

    # Resolve parent_id for DB query
    if folder_id is None or folder_id == "root":
        parent_id_obj: Optional[PydanticObjectId] = None
        current_folder = None
        breadcrumb_text = "🏠 **Root**"
        back_parent_id = None
    else:
        try:
            parent_id_obj = PydanticObjectId(folder_id)
        except Exception:
            if isinstance(update, CallbackQuery):
                await update.answer("❌ Invalid folder ID.", show_alert=True)
            return
        current_folder = await folder_service.get_folder(parent_id_obj)
        if current_folder is None:
            if isinstance(update, CallbackQuery):
                await update.answer("❌ Folder not found.", show_alert=True)
            return
        crumbs = await folder_service.get_breadcrumbs(parent_id_obj)
        crumb_parts = ["🏠 Root"] + [f"📁 {escape_markdown(c.name)}" for c in crumbs]
        breadcrumb_text = "  ›  ".join(crumb_parts)
        back_parent_id = (
            str(current_folder.parent_id) if current_folder.parent_id else "root"
        )

    # Fetch contents concurrently
    folders, files = await asyncio.gather(
        folder_service.get_children(parent_id_obj),
        file_service.get_files_in_folder(parent_id_obj),
    )

    # Build message text
    folder_count = len(folders)
    file_count = len(files)
    text = (
        f"{breadcrumb_text}\n\n"
        f"📁 {folder_count} folder{'s' if folder_count != 1 else ''}  "
        f"🎬 {file_count} file{'s' if file_count != 1 else ''}"
    )

    # Compute IDs for keyboard builder
    current_id = folder_id if (folder_id and folder_id != "root") else "root"

    # Build keyboard
    if folder_count == 0 and file_count == 0:
        keyboard = build_empty_folder_keyboard(
            current_id=current_id,
            back_id=back_parent_id,
            is_admin=is_admin,
        )
        if is_admin:
            text += "\n\n_This folder is empty. Tap ➕ New Folder or 📤 Upload below to add content._"
        else:
            text += "\n\n_This folder is empty._"
    else:
        keyboard = build_folder_keyboard(
            folders=folders,
            files=files,
            page=page,
            current_id=current_id,
            back_id=back_parent_id,
            is_admin=is_admin,
        )

    # Render
    if isinstance(update, CallbackQuery):
        try:
            await update.edit_message_text(
                text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            pass  # Message content unchanged — ignore "not modified" error
    else:
        await update.reply(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

# ── nav:{folder_id}:{page} callback ──────────────────────────────────────────


@bot.on_callback_query(filters.regex(r"^nav:"))
@approved_and_above
async def nav_callback(client, query: CallbackQuery, user: User) -> None:
    """Browse into a folder."""
    await query.answer()
    parts = decode(query.data)
    # parts = ("nav", folder_id, page)
    folder_id = parts[1] if len(parts) > 1 else "root"
    page = int(parts[2]) if len(parts) > 2 else 1
    await render_folder(client, query, folder_id=folder_id, page=page, user=user)

# ── back:{parent_id} callback ─────────────────────────────────────────────────


@bot.on_callback_query(filters.regex(r"^back:"))
@approved_and_above
async def back_callback(client, query: CallbackQuery, user: User) -> None:
    """Navigate to the parent folder."""
    await query.answer()
    parts = decode(query.data)
    parent_id = parts[1] if len(parts) > 1 else "root"
    await render_folder(client, query, folder_id=parent_id, page=1, user=user)

# ── noop callback (page indicator button) ─────────────────────────────────────


@bot.on_callback_query(filters.regex(r"^noop$"))
async def noop_callback(client, query: CallbackQuery) -> None:
    """Page indicator button — does nothing, just answers the callback."""
    await query.answer()

# ── fi:{folder_id} — Folder action menu ──────────────────────────────────────


@bot.on_callback_query(filters.regex(r"^fi:"))
@owner_only
async def folder_info_callback(client, query: CallbackQuery, user: User) -> None:
    """Show admin action menu for a specific folder (⚙️ button)."""
    await query.answer()
    parts = decode(query.data)
    folder_id = parts[1]

    folder = await folder_service.get_folder(PydanticObjectId(folder_id))
    if folder is None:
        await query.answer("❌ Folder not found.", show_alert=True)
        return

    parent_id_str = str(folder.parent_id) if folder.parent_id else "root"
    await query.edit_message_text(
        f"⚙️ **Folder Actions**\n\n📁 {escape_markdown(folder.name)}",
        reply_markup=folder_actions_kb(folder_id, parent_id_str),
        parse_mode=ParseMode.MARKDOWN,
    )

# ── fli:{file_id} — File action menu ─────────────────────────────────────────


@bot.on_callback_query(filters.regex(r"^fli:"))
@owner_only
async def file_info_callback(client, query: CallbackQuery, user: User) -> None:
    """Show admin action menu for a specific file (⚙️ button)."""
    await query.answer()
    parts = decode(query.data)
    file_doc_id = parts[1]

    file_doc = await file_service.get_file(PydanticObjectId(file_doc_id))
    if file_doc is None:
        await query.answer("❌ File not found.", show_alert=True)
        return

    await query.edit_message_text(
        f"⚙️ **File Actions**\n\n🎬 {escape_markdown(file_doc.name)}\n__{escape_markdown(file_doc.display_meta)}__",
        reply_markup=file_actions_kb(file_doc_id, str(file_doc.folder_id)),
        parse_mode=ParseMode.MARKDOWN,
    )
