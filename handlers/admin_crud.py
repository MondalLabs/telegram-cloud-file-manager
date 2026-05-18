"""
handlers/admin_crud.py
─────────────────────────────────────────────────────────────────────────────
All CRUD FSM workflows for folder and file management (Owner only).

FSM states used:
  "create_folder:waiting_name"   data: {parent_id}
  "rename_folder:waiting_name"   data: {folder_id, back_folder_id}
  "rename_file:waiting_name"     data: {file_doc_id, folder_id}

Confirmation (delete) is handled statelessly — the action+target_id is
encoded directly into the confirm button's callback_data, so no FSM state
is needed for delete confirmations.

Callback patterns handled:
  cf:{parent_id}               — start Create Folder FSM
  rf:{folder_id}               — start Rename Folder FSM
  df:{folder_id}               — show Delete Folder confirmation
  renf:{file_doc_id}           — start Rename File FSM
  delf:{file_doc_id}           — show Delete File confirmation
  yes:{action}:{target_id}     — execute confirmed destructive action
  cancel                       — abort current FSM
  /cancel command              — abort current FSM via command
"""

from __future__ import annotations

import logging
from typing import Optional

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message, CallbackQuery
from beanie import PydanticObjectId

from bot.client import bot
from models.user import User, UserRole
from middlewares.access_control import owner_only
from keyboards.confirm_kb import confirm_delete_kb, cancel_only_kb
from keyboards.admin_kb import admin_dashboard_kb
import services.folder_service as folder_service
import services.file_service as file_service
import services.fsm_service as fsm_service
from utils.callback_data import (
    decode, encode,
    ACTION_CF, ACTION_RF, ACTION_DF,
    ACTION_REN_FILE, ACTION_DEL_FILE,
    ACTION_CONFIRM, ACTION_CANCEL,
    ACTION_NAV, ACTION_USR_REVOKE,
)

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: navigate back to a folder after an operation
# ─────────────────────────────────────────────────────────────────────────────

async def _refresh_folder(client, update: Message | CallbackQuery, folder_id: Optional[str], user: User) -> None:
    """Refresh the folder listing view after a CRUD operation."""
    from handlers.navigation import render_folder
    await render_folder(client, update, folder_id=folder_id, page=1, user=user)


# ─────────────────────────────────────────────────────────────────────────────
# CANCEL — abort any active FSM
# ─────────────────────────────────────────────────────────────────────────────

@bot.on_message(filters.command("cancel") & filters.private)
@owner_only
async def cancel_command(client, message: Message, user: User) -> None:
    """Abort the active FSM workflow."""
    await fsm_service.clear_state(user.telegram_id)
    await message.reply(
        "❌ Operation cancelled.",
        reply_markup=admin_dashboard_kb(),
    )


@bot.on_callback_query(filters.regex(r"^cancel$"))
@owner_only
async def cancel_callback(client, query: CallbackQuery, user: User) -> None:
    """Abort the active FSM workflow from a button."""
    await query.answer("Cancelled.")
    await fsm_service.clear_state(user.telegram_id)
    await query.edit_message_text(
        "❌ Operation cancelled.",
        reply_markup=admin_dashboard_kb(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# CREATE FOLDER FSM
# ─────────────────────────────────────────────────────────────────────────────

@bot.on_callback_query(filters.regex(r"^cf:"))
@owner_only
async def create_folder_start(client, query: CallbackQuery, user: User) -> None:
    """Start the Create Folder FSM: ask for a folder name."""
    await query.answer()
    parts = decode(query.data)
    parent_id = parts[1]  # "root" or a 24-char ObjectId string

    await fsm_service.set_state(
        user.telegram_id,
        state="create_folder:waiting_name",
        data={"parent_id": parent_id},
    )
    await query.edit_message_text(
        "📁 **Create New Folder**\n\n"
        "Send the folder name as a message.\n"
        "Or tap Cancel to abort.",
        reply_markup=cancel_only_kb(),
        parse_mode=ParseMode.MARKDOWN,
    )


# ─────────────────────────────────────────────────────────────────────────────
# RENAME FOLDER FSM
# ─────────────────────────────────────────────────────────────────────────────

@bot.on_callback_query(filters.regex(r"^rf:"))
@owner_only
async def rename_folder_start(client, query: CallbackQuery, user: User) -> None:
    """Start the Rename Folder FSM: ask for new name."""
    await query.answer()
    parts = decode(query.data)
    folder_id = parts[1]

    folder = await folder_service.get_folder(PydanticObjectId(folder_id))
    if folder is None:
        await query.answer("❌ Folder not found.", show_alert=True)
        return

    back_id = str(folder.parent_id) if folder.parent_id else "root"
    await fsm_service.set_state(
        user.telegram_id,
        state="rename_folder:waiting_name",
        data={"folder_id": folder_id, "back_folder_id": back_id},
    )
    await query.edit_message_text(
        f"✏️ **Rename Folder**\n\n"
        f"Current name: **{folder.name}**\n\n"
        f"Send the new folder name.\n"
        f"Or tap Cancel to abort.",
        reply_markup=cancel_only_kb(),
        parse_mode=ParseMode.MARKDOWN,
    )


# ─────────────────────────────────────────────────────────────────────────────
# DELETE FOLDER — show confirmation (stateless)
# ─────────────────────────────────────────────────────────────────────────────

@bot.on_callback_query(filters.regex(r"^df:"))
@owner_only
async def delete_folder_confirm(client, query: CallbackQuery, user: User) -> None:
    """Show the delete confirmation keyboard for a folder."""
    await query.answer()
    parts = decode(query.data)
    folder_id = parts[1]

    folder = await folder_service.get_folder(PydanticObjectId(folder_id))
    if folder is None:
        await query.answer("❌ Folder not found.", show_alert=True)
        return

    await query.edit_message_text(
        f"🗑️ **Delete Folder**\n\n"
        f"📁 **{folder.name}**\n\n"
        f"⚠️ This will permanently delete this folder AND all its "
        f"sub-folders and files. This cannot be undone.",
        reply_markup=confirm_delete_kb(ACTION_DF, folder_id, label="Delete"),
        parse_mode=ParseMode.MARKDOWN,
    )


# ─────────────────────────────────────────────────────────────────────────────
# RENAME FILE FSM
# ─────────────────────────────────────────────────────────────────────────────

@bot.on_callback_query(filters.regex(r"^renf:"))
@owner_only
async def rename_file_start(client, query: CallbackQuery, user: User) -> None:
    """Start the Rename File FSM: ask for new name."""
    await query.answer()
    parts = decode(query.data)
    file_doc_id = parts[1]

    file_doc = await file_service.get_file(PydanticObjectId(file_doc_id))
    if file_doc is None:
        await query.answer("❌ File not found.", show_alert=True)
        return

    await fsm_service.set_state(
        user.telegram_id,
        state="rename_file:waiting_name",
        data={"file_doc_id": file_doc_id, "folder_id": str(file_doc.folder_id)},
    )
    await query.edit_message_text(
        f"✏️ **Rename File**\n\n"
        f"Current name: **{file_doc.name}**\n\n"
        f"Send the new file name.\n"
        f"Or tap Cancel to abort.",
        reply_markup=cancel_only_kb(),
        parse_mode=ParseMode.MARKDOWN,
    )


# ─────────────────────────────────────────────────────────────────────────────
# DELETE FILE — show confirmation (stateless)
# ─────────────────────────────────────────────────────────────────────────────

@bot.on_callback_query(filters.regex(r"^delf:"))
@owner_only
async def delete_file_confirm(client, query: CallbackQuery, user: User) -> None:
    """Show the delete confirmation keyboard for a file."""
    await query.answer()
    parts = decode(query.data)
    file_doc_id = parts[1]

    file_doc = await file_service.get_file(PydanticObjectId(file_doc_id))
    if file_doc is None:
        await query.answer("❌ File not found.", show_alert=True)
        return

    await query.edit_message_text(
        f"🗑️ **Delete File**\n\n"
        f"🎬 **{file_doc.name}**\n"
        f"__{file_doc.display_meta}__\n\n"
        f"⚠️ This will remove the file from the library. "
        f"The video remains in the CDN but will be inaccessible.",
        reply_markup=confirm_delete_kb(ACTION_DEL_FILE, file_doc_id, label="Delete"),
        parse_mode=ParseMode.MARKDOWN,
    )


# ─────────────────────────────────────────────────────────────────────────────
# YES:{action}:{target_id} — execute confirmed destructive action
# ─────────────────────────────────────────────────────────────────────────────

@bot.on_callback_query(filters.regex(r"^yes:"))
@owner_only
async def confirm_action(client, query: CallbackQuery, user: User) -> None:
    """Execute the confirmed destructive action."""
    await query.answer()
    parts = decode(query.data)
    # parts = ("yes", action, target_id)
    if len(parts) < 3:
        return
    action, target_id = parts[1], parts[2]

    if action == ACTION_DF:
        # Delete folder tree
        try:
            result = await folder_service.delete_folder_tree(PydanticObjectId(target_id))
            await query.edit_message_text(
                f"✅ **Deleted**\n\n"
                f"Removed {result['folders_deleted']} folder(s) and "
                f"{result['files_deleted']} file(s).",
                reply_markup=admin_dashboard_kb(),
            )
        except Exception as e:
            log.error("delete_folder_tree error: %s", e)
            await query.edit_message_text(f"❌ Error: {e}", reply_markup=admin_dashboard_kb())

    elif action == ACTION_DEL_FILE:
        # Delete single file
        success = await file_service.delete_file(PydanticObjectId(target_id))
        if success:
            await query.edit_message_text(
                "✅ File deleted successfully.",
                reply_markup=admin_dashboard_kb(),
            )
        else:
            await query.edit_message_text(
                "❌ File not found — may have already been deleted.",
                reply_markup=admin_dashboard_kb(),
            )

    elif action == ACTION_USR_REVOKE:
        # Revoke user access — routed here because confirm_action owns all yes: callbacks
        import services.user_service as _user_svc
        from keyboards.admin_kb import user_management_kb as _umgmt_kb
        target = await _user_svc.find_user_by_id_doc(target_id)
        if target is None:
            await query.edit_message_text("❌ User not found.", reply_markup=admin_dashboard_kb())
            return
        await _user_svc.revoke_user(target.telegram_id)
        await query.edit_message_text(
            f"✅ **Access Revoked**\n\n"
            f"**{target.display_name}** (`{target.telegram_id}`) "
            f"has been downgraded to Guest.",
            reply_markup=_umgmt_kb(),
            parse_mode=ParseMode.MARKDOWN,
        )

    else:
        await query.edit_message_text("❌ Unknown action.", reply_markup=admin_dashboard_kb())


# ─────────────────────────────────────────────────────────────────────────────
# FSM TEXT ROUTER — processes name inputs for active FSM states
# ─────────────────────────────────────────────────────────────────────────────

@bot.on_message(filters.text & filters.private & ~filters.command(["start", "cancel", "done"]))
@owner_only
async def fsm_text_router(client, message: Message, user: User) -> None:
    """
    Routes incoming text messages from the owner to the active FSM state handler.
    If no state is active, silently ignore (the guest handler won't fire for owners).
    """
    state, data = await fsm_service.get_state_and_data(user.telegram_id)

    if state == "create_folder:waiting_name":
        await _handle_create_folder(client, message, user, data)

    elif state == "rename_folder:waiting_name":
        await _handle_rename_folder(client, message, user, data)

    elif state == "rename_file:waiting_name":
        await _handle_rename_file(client, message, user, data)

    elif state is None:
        # Owner sent a text with no active FSM — show the dashboard
        await message.reply(
            "ℹ️ Use the buttons below to navigate.",
            reply_markup=admin_dashboard_kb(),
        )


async def _handle_create_folder(client, message: Message, user: User, data: dict) -> None:
    """Process the folder name input for the Create Folder FSM."""
    name = message.text.strip()
    parent_id_str = data.get("parent_id", "root")
    parent_id_obj = PydanticObjectId(parent_id_str) if parent_id_str != "root" else None

    try:
        folder = await folder_service.create_folder(
            name=name,
            parent_id=parent_id_obj,
            created_by=user.telegram_id,
        )
        await fsm_service.clear_state(user.telegram_id)
        await message.reply(f"✅ Folder **{folder.name}** created.", parse_mode=ParseMode.MARKDOWN)
        await _refresh_folder(client, message, folder_id=parent_id_str, user=user)
    except ValueError as e:
        await message.reply(f"⚠️ {e}\n\nSend a different name or tap Cancel to abort.", reply_markup=cancel_only_kb())


async def _handle_rename_folder(client, message: Message, user: User, data: dict) -> None:
    """Process the new name input for the Rename Folder FSM."""
    new_name = message.text.strip()
    folder_id = data.get("folder_id")
    back_folder_id = data.get("back_folder_id", "root")

    try:
        folder = await folder_service.rename_folder(PydanticObjectId(folder_id), new_name)
        await fsm_service.clear_state(user.telegram_id)
        await message.reply(f"✅ Renamed to **{folder.name}**.", parse_mode=ParseMode.MARKDOWN)
        await _refresh_folder(client, message, folder_id=back_folder_id, user=user)
    except ValueError as e:
        await message.reply(f"⚠️ {e}\n\nSend a different name or tap Cancel to abort.", reply_markup=cancel_only_kb())


async def _handle_rename_file(client, message: Message, user: User, data: dict) -> None:
    """Process the new name input for the Rename File FSM."""
    new_name = message.text.strip()
    file_doc_id = data.get("file_doc_id")
    folder_id = data.get("folder_id", "root")

    file_doc = await file_service.rename_file(PydanticObjectId(file_doc_id), new_name)
    await fsm_service.clear_state(user.telegram_id)
    if file_doc:
        await message.reply(f"✅ Renamed to **{file_doc.name}**.", parse_mode=ParseMode.MARKDOWN)
    else:
        await message.reply("❌ File not found.")
    await _refresh_folder(client, message, folder_id=folder_id, user=user)
