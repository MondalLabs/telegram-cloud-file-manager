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
from utils.sanitize import escape_markdown

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
@approved_and_above
async def cancel_command(client, message: Message, user: User) -> None:
    """Abort the active FSM workflow."""
    state, data = await fsm_service.get_state_and_data(user.telegram_id)
    await fsm_service.clear_state(user.telegram_id)

    if state == "upload:waiting_files" and data:
        instruction_msg_id = data.get("instruction_msg_id")
        if instruction_msg_id:
            try:
                await client.delete_messages(message.chat.id, instruction_msg_id)
            except Exception:
                pass

    folder_id = None
    has_context = False

    if data:
        if "parent_id" in data:
            folder_id = data.get("parent_id")
            has_context = True
        elif "back_folder_id" in data:
            folder_id = data.get("back_folder_id")
            has_context = True
        elif "folder_id" in data:
            folder_id = data.get("folder_id")
            has_context = True
        elif data.get("from_menu") == "usrmenu":
            from keyboards.admin_kb import user_management_kb
            await message.reply(
                "❌ Operation cancelled.\n\n👤 **User Management**\n\nManage user access to the library.",
                reply_markup=user_management_kb(),
                parse_mode=ParseMode.MARKDOWN,
            )
            return

    if has_context:
        await message.reply("❌ Operation cancelled.")
        from handlers.navigation import render_folder
        await render_folder(client, message, folder_id=str(folder_id) if folder_id else "root", page=1, user=user)
    else:
        if user.role == UserRole.OWNER:
            await message.reply(
                "❌ Operation cancelled.",
                reply_markup=admin_dashboard_kb(),
            )
        else:
            await message.reply("❌ Operation cancelled.")
            from handlers.navigation import render_folder
            await render_folder(client, message, folder_id="root", page=1, user=user)

@bot.on_callback_query(filters.regex(r"^cancel$"))
@approved_and_above
async def cancel_callback(client, query: CallbackQuery, user: User) -> None:
    """Abort the active FSM workflow via inline button."""
    state, data = await fsm_service.get_state_and_data(user.telegram_id)
    await fsm_service.clear_state(user.telegram_id)

    folder_id = None
    has_context = False

    if data:
        if "parent_id" in data:
            folder_id = data.get("parent_id")
            has_context = True
        elif "back_folder_id" in data:
            folder_id = data.get("back_folder_id")
            has_context = True
        elif "folder_id" in data:
            folder_id = data.get("folder_id")
            has_context = True
        elif data.get("from_menu") == "usrmenu":
            await query.answer("Operation cancelled.")
            from keyboards.admin_kb import user_management_kb
            await query.edit_message_text(
                "👤 **User Management**\n\nManage user access to the library.",
                reply_markup=user_management_kb(),
                parse_mode=ParseMode.MARKDOWN,
            )
            return

    if has_context:
        await query.answer("Operation cancelled.")
        from handlers.navigation import render_folder
        await render_folder(client, query, folder_id=str(folder_id) if folder_id else "root", page=1, user=user)
    else:
        await query.answer()
        if user.role == UserRole.OWNER:
            await query.edit_message_text(
                "❌ Operation cancelled.",
                reply_markup=admin_dashboard_kb(),
            )
        else:
            from handlers.navigation import render_folder
            await render_folder(client, query, folder_id="root", page=1, user=user)

# ─────────────────────────────────────────────────────────────────────────────
# CREATE FOLDER FSM
# ─────────────────────────────────────────────────────────────────────────────

@bot.on_callback_query(filters.regex(r"^cf:"))
@approved_and_above
async def create_folder_start(client, query: CallbackQuery, user: User) -> None:
    """Start the Create Folder FSM: ask for a folder name."""
    if user.role != UserRole.OWNER and not getattr(user, "can_create_folder", False):
        await query.answer("⛔ Access Denied: You do not have permission to create folders.", show_alert=True)
        return
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
@approved_and_above
async def rename_folder_start(client, query: CallbackQuery, user: User) -> None:
    """Start the Rename Folder FSM: ask for new name."""
    if user.role != UserRole.OWNER and not getattr(user, "can_rename", False):
        await query.answer("⛔ Access Denied: You do not have permission to rename folders.", show_alert=True)
        return
    await query.answer()
    parts = decode(query.data)
    folder_id = parts[1]

    if not PydanticObjectId.is_valid(folder_id):
        await query.answer("❌ Invalid folder ID.", show_alert=True)
        return

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
        f"Current name: **{escape_markdown(folder.name)}**\n\n"
        f"Send the new folder name.\n"
        f"Or tap Cancel to abort.",
        reply_markup=cancel_only_kb(),
        parse_mode=ParseMode.MARKDOWN,
    )

# ─────────────────────────────────────────────────────────────────────────────
# DELETE FOLDER — show confirmation (stateless)
# ─────────────────────────────────────────────────────────────────────────────

@bot.on_callback_query(filters.regex(r"^df:"))
@approved_and_above
async def delete_folder_confirm(client, query: CallbackQuery, user: User) -> None:
    """Show the delete confirmation keyboard for a folder."""
    if user.role != UserRole.OWNER and not getattr(user, "can_delete", False):
        await query.answer("Spacer: You do not have permission to delete folders.", show_alert=True)
        return
    await query.answer()
    parts = decode(query.data)
    folder_id = parts[1]

    if not PydanticObjectId.is_valid(folder_id):
        await query.answer("❌ Invalid folder ID.", show_alert=True)
        return

    folder = await folder_service.get_folder(PydanticObjectId(folder_id))
    if folder is None:
        await query.answer("❌ Folder not found.", show_alert=True)
        return

    parent_id = str(folder.parent_id) if folder.parent_id else "root"
    cancel_data = encode(ACTION_NAV, parent_id, 1)

    await query.edit_message_text(
        f"🗑️ **Delete Folder**\n\n"
        f"📁 **{escape_markdown(folder.name)}**\n\n"
        f"⚠️ This will permanently delete this folder AND all its "
        f"sub-folders and files. This cannot be undone.",
        reply_markup=confirm_delete_kb(ACTION_DF, folder_id, cancel_data=cancel_data, label="Delete"),
        parse_mode=ParseMode.MARKDOWN,
    )

# ─────────────────────────────────────────────────────────────────────────────
# RENAME FILE FSM
# ─────────────────────────────────────────────────────────────────────────────

@bot.on_callback_query(filters.regex(r"^renf:"))
@approved_and_above
async def rename_file_start(client, query: CallbackQuery, user: User) -> None:
    """Start the Rename File FSM: ask for new name."""
    if user.role != UserRole.OWNER and not getattr(user, "can_rename", False):
        await query.answer("⛔ Access Denied: You do not have permission to rename files.", show_alert=True)
        return
    await query.answer()
    parts = decode(query.data)
    file_doc_id = parts[1]

    if not PydanticObjectId.is_valid(file_doc_id):
        await query.answer("❌ Invalid file ID.", show_alert=True)
        return

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
        f"Current name: **{escape_markdown(file_doc.name)}**\n\n"
        f"Send the new file name.\n"
        f"Or tap Cancel to abort.",
        reply_markup=cancel_only_kb(),
        parse_mode=ParseMode.MARKDOWN,
    )

# ─────────────────────────────────────────────────────────────────────────────
# DELETE FILE — show confirmation (stateless)
# ─────────────────────────────────────────────────────────────────────────────

@bot.on_callback_query(filters.regex(r"^delf:"))
@approved_and_above
async def delete_file_confirm(client, query: CallbackQuery, user: User) -> None:
    """Show the delete confirmation keyboard for a file."""
    if user.role != UserRole.OWNER and not getattr(user, "can_delete", False):
        await query.answer("⛔ Access Denied: You do not have permission to delete files.", show_alert=True)
        return
    await query.answer()
    parts = decode(query.data)
    file_doc_id = parts[1]

    if not PydanticObjectId.is_valid(file_doc_id):
        await query.answer("❌ Invalid file ID.", show_alert=True)
        return

    file_doc = await file_service.get_file(PydanticObjectId(file_doc_id))
    if file_doc is None:
        await query.answer("❌ File not found.", show_alert=True)
        return

    folder_id = str(file_doc.folder_id) if file_doc.folder_id else "root"
    cancel_data = encode(ACTION_NAV, folder_id, 1)

    await query.edit_message_text(
        f"🗑️ **Delete File**\n\n"
        f"🎬 **{escape_markdown(file_doc.name)}**\n"
        f"__{escape_markdown(file_doc.display_meta)}__\n\n"
        f"⚠️ This will remove the file from the library. "
        f"The video remains in the CDN but will be inaccessible.",
        reply_markup=confirm_delete_kb(ACTION_DEL_FILE, file_doc_id, cancel_data=cancel_data, label="Delete"),
        parse_mode=ParseMode.MARKDOWN,
    )

# ─────────────────────────────────────────────────────────────────────────────
# YES:{action}:{target_id} — execute confirmed destructive action
# ─────────────────────────────────────────────────────────────────────────────

@bot.on_callback_query(filters.regex(r"^yes:"))
@approved_and_above
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
        if user.role != UserRole.OWNER and not getattr(user, "can_delete", False):
            await query.answer("⛔ Access Denied: You do not have folder deletion permission.", show_alert=True)
            return
        if not PydanticObjectId.is_valid(target_id):
            await query.answer("❌ Invalid folder ID.", show_alert=True)
            return
        folder = await folder_service.get_folder(PydanticObjectId(target_id))
        parent_id = str(folder.parent_id) if folder and folder.parent_id else "root"
        try:
            result = await folder_service.delete_folder_tree(PydanticObjectId(target_id))
            await query.answer(f"Deleted {result['folders_deleted']} folders and {result['files_deleted']} files.")
            from handlers.navigation import render_folder
            await render_folder(client, query, folder_id=parent_id, page=1, user=user)
        except Exception as e:
            log.error("delete_folder_tree error: %s", e)
            if user.role == UserRole.OWNER:
                await query.edit_message_text("❌ Internal Error: Could not delete folder tree.", reply_markup=admin_dashboard_kb())
            else:
                await query.edit_message_text("❌ Internal Error: Could not delete folder tree.")
                from handlers.navigation import render_folder
                await render_folder(client, query, folder_id="root", page=1, user=user)

    elif action == ACTION_DEL_FILE:
        # Delete single file
        if user.role != UserRole.OWNER and not getattr(user, "can_delete", False):
            await query.answer("⛔ Access Denied: You do not have file deletion permission.", show_alert=True)
            return
        if not PydanticObjectId.is_valid(target_id):
            await query.answer("❌ Invalid file ID.", show_alert=True)
            return
        file_doc = await file_service.get_file(PydanticObjectId(target_id))
        folder_id = str(file_doc.folder_id) if file_doc and file_doc.folder_id else "root"
        success = await file_service.delete_file(PydanticObjectId(target_id))
        if success:
            await query.answer("File deleted successfully.")
        else:
            await query.answer("File not found — may have already been deleted.", show_alert=True)
        from handlers.navigation import render_folder
        await render_folder(client, query, folder_id=folder_id, page=1, user=user)

    elif action == ACTION_USR_REVOKE:
        # Revoke user access — routed here because confirm_action owns all yes: callbacks
        if user.role != UserRole.OWNER:
            await query.answer("⛔ Access Denied: Super-admin only.", show_alert=True)
            return
        import services.user_service as _user_svc
        from keyboards.admin_kb import user_management_kb as _umgmt_kb
        target = await _user_svc.find_user_by_id_doc(target_id)
        if target is None:
            await query.edit_message_text("❌ User not found.", reply_markup=admin_dashboard_kb())
            return
        await _user_svc.revoke_user(target.telegram_id)
        await query.edit_message_text(
            f"✅ **Access Revoked**\n\n"
            f"**{escape_markdown(target.display_name)}** (`{target.telegram_id}`) "
            f"has been downgraded to Guest.",
            reply_markup=_umgmt_kb(),
            parse_mode=ParseMode.MARKDOWN,
        )

    else:
        if user.role == UserRole.OWNER:
            await query.edit_message_text("❌ Unknown action.", reply_markup=admin_dashboard_kb())
        else:
            await query.edit_message_text("❌ Unknown action.")

# ─────────────────────────────────────────────────────────────────────────────
# FSM TEXT ROUTER — processes name inputs for active FSM states
# ─────────────────────────────────────────────────────────────────────────────

@bot.on_message(filters.text & filters.private & ~filters.command(["start", "cancel", "done"]))
@approved_and_above
async def fsm_text_router(client, message: Message, user: User) -> None:
    """
    Routes incoming text messages from the approved user to the active FSM state handler.
    If no state is active, silently ignore.
    """
    state, data = await fsm_service.get_state_and_data(user.telegram_id)

    if state == "create_folder:waiting_name":
        if user.role != UserRole.OWNER and not getattr(user, "can_create_folder", False):
            await message.reply("⛔ Access Denied: You do not have folder creation permission.")
            await fsm_service.clear_state(user.telegram_id)
            return
        await _handle_create_folder(client, message, user, data)

    elif state == "rename_folder:waiting_name":
        if user.role != UserRole.OWNER and not getattr(user, "can_rename", False):
            await message.reply("⛔ Access Denied: You do not have folder rename permission.")
            await fsm_service.clear_state(user.telegram_id)
            return
        await _handle_rename_folder(client, message, user, data)

    elif state == "rename_file:waiting_name":
        if user.role != UserRole.OWNER and not getattr(user, "can_rename", False):
            await message.reply("⛔ Access Denied: You do not have file rename permission.")
            await fsm_service.clear_state(user.telegram_id)
            return
        await _handle_rename_file(client, message, user, data)

    elif state is None:
        if user.role == UserRole.OWNER:
            # Owner sent a text with no active FSM — show the dashboard
            await message.reply(
                "ℹ️ Use the buttons below to navigate.",
                reply_markup=admin_dashboard_kb(),
            )
        else:
            # For non-owners, redirect them to the home folder listing
            from handlers.navigation import render_folder
            await render_folder(client, message, folder_id="root", page=1, user=user)

async def _handle_create_folder(client, message: Message, user: User, data: dict) -> None:
    """Process the folder name input for the Create Folder FSM."""
    name = message.text.strip()
    if len(name) > 128:
        await message.reply("⚠️ Folder name is too long (max 128 characters).\n\nSend a shorter name or tap Cancel to abort.", reply_markup=cancel_only_kb())
        return

    parent_id_str = data.get("parent_id", "root")

    if parent_id_str != "root" and not PydanticObjectId.is_valid(parent_id_str):
        await message.reply("❌ Invalid parent folder ID. Please start over.", reply_markup=cancel_only_kb())
        await fsm_service.clear_state(user.telegram_id)
        return

    parent_id_obj = PydanticObjectId(parent_id_str) if parent_id_str != "root" else None

    try:
        folder = await folder_service.create_folder(
            name=name,
            parent_id=parent_id_obj,
            created_by=user.telegram_id,
        )
        await fsm_service.clear_state(user.telegram_id)
        await message.reply(f"✅ Folder **{escape_markdown(folder.name)}** created.", parse_mode=ParseMode.MARKDOWN)
        await _refresh_folder(client, message, folder_id=parent_id_str, user=user)
    except ValueError as e:
        log.error("Create folder error: %s", e)
        await message.reply("⚠️ Invalid folder name.\n\nSend a different name or tap Cancel to abort.", reply_markup=cancel_only_kb())


async def _handle_rename_folder(client, message: Message, user: User, data: dict) -> None:
    """Process the new name input for the Rename Folder FSM."""
    new_name = message.text.strip()
    if len(new_name) > 128:
        await message.reply("⚠️ Folder name is too long (max 128 characters).\n\nSend a shorter name or tap Cancel to abort.", reply_markup=cancel_only_kb())
        return

    folder_id = data.get("folder_id")
    back_folder_id = data.get("back_folder_id", "root")

    if not PydanticObjectId.is_valid(folder_id):
        await message.reply("❌ Invalid folder ID. Please start over.", reply_markup=cancel_only_kb())
        await fsm_service.clear_state(user.telegram_id)
        return

    try:
        folder = await folder_service.rename_folder(PydanticObjectId(folder_id), new_name)
        await fsm_service.clear_state(user.telegram_id)
        await message.reply(f"✅ Renamed to **{escape_markdown(folder.name)}**.", parse_mode=ParseMode.MARKDOWN)
        await _refresh_folder(client, message, folder_id=back_folder_id, user=user)
    except ValueError as e:
        log.error("Rename folder error: %s", e)
        await message.reply("⚠️ Invalid folder name.\n\nSend a different name or tap Cancel to abort.", reply_markup=cancel_only_kb())


async def _handle_rename_file(client, message: Message, user: User, data: dict) -> None:
    """Process the new name input for the Rename File FSM."""
    new_name = message.text.strip()
    if len(new_name) > 128:
        await message.reply("⚠️ File name is too long (max 128 characters).\n\nSend a shorter name or tap Cancel to abort.", reply_markup=cancel_only_kb())
        return

    file_doc_id = data.get("file_doc_id")
    folder_id = data.get("folder_id", "root")

    if not PydanticObjectId.is_valid(file_doc_id):
        await message.reply("❌ Invalid file ID. Please start over.", reply_markup=cancel_only_kb())
        await fsm_service.clear_state(user.telegram_id)
        return

    file_doc = await file_service.rename_file(PydanticObjectId(file_doc_id), new_name)
    await fsm_service.clear_state(user.telegram_id)
    if file_doc:
        await message.reply(f"✅ Renamed to **{escape_markdown(file_doc.name)}**.", parse_mode=ParseMode.MARKDOWN)
    else:
        await message.reply("❌ File not found.")
    await _refresh_folder(client, message, folder_id=folder_id, user=user)


# ── CDN Health Check ──────────────────────────────────────────────────────────

@bot.on_callback_query(filters.regex(r"^healthcheck$"))
@owner_only
async def run_health_check_callback(client, query: CallbackQuery, user: User) -> None:
    """Scan all files in the database and verify their existence in the Telegram dump group CDN."""
    await query.answer()

    from models.settings import BotSettings
    from models.file import File
    from bot.config import settings as cfg
    import services.folder_service as folder_service
    import asyncio

    dump_chat_id = await BotSettings.get_dump_chat_id(fallback=cfg.dump_chat_id)
    if dump_chat_id is None:
        await query.edit_message_text(
            "❌ **Health Check Aborted**\n\nDump storage group is not configured. Please run /setup inside the dump group first.",
            reply_markup=admin_dashboard_kb(),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    await query.edit_message_text(
        "🩺 **CDN Health Check**\n\nRetrieving file references from database...",
        parse_mode=ParseMode.MARKDOWN,
    )

    all_files = await File.find_all().to_list()
    total_files = len(all_files)

    if total_files == 0:
        await query.edit_message_text(
            "🩺 **CDN Health Report**\n\nTotal Files: **0**\n\n✅ Library is empty. Nothing to verify.",
            reply_markup=admin_dashboard_kb(),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Categorize files
    legacy_files = []
    verifiable_files = []

    for f in all_files:
        if f.dump_message_id is None:
            legacy_files.append(f)
        else:
            verifiable_files.append(f)

    missing_files = []
    verified_count = 0
    scanned_count = 0
    total_verifiable = len(verifiable_files)

    # Batch verification
    batch_size = 200
    for i in range(0, total_verifiable, batch_size):
        batch = verifiable_files[i : i + batch_size]
        msg_ids = [f.dump_message_id for f in batch]

        # Show progress
        progress_text = (
            f"🩺 **CDN Health Check**\n\n"
            f"Scanning: **{scanned_count + len(legacy_files)}/{total_files}** files processed...\n"
            f"Verified active: **{verified_count}**\n"
            f"Detected missing: **{len(missing_files)}**"
        )
        try:
            await query.edit_message_text(progress_text, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            pass  # Ignore unchanged progress edits

        try:
            tg_msgs = await client.get_messages(chat_id=dump_chat_id, message_ids=msg_ids)
            if not isinstance(tg_msgs, list):
                tg_msgs = [tg_msgs]
        except Exception as e:
            log.error("Error fetching messages in batch: %s", e)
            await query.edit_message_text(
                "❌ **Health Check Error**\n\nCould not query dump group due to an internal error.",
                reply_markup=admin_dashboard_kb(),
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        # Map results
        for idx, f in enumerate(batch):
            tg_msg = tg_msgs[idx] if idx < len(tg_msgs) else None
            is_deleted = tg_msg is None or getattr(tg_msg, "empty", False)

            if is_deleted:
                # Resolve folder path
                path_str = "Root"
                if f.folder_id:
                    try:
                        crumbs = await folder_service.get_breadcrumbs(f.folder_id)
                        path_str = " > ".join(c.name for c in crumbs)
                    except Exception:
                        path_str = "Unknown Folder"
                missing_files.append((f, path_str))
            else:
                verified_count += 1

        scanned_count += len(batch)

        # Rate limit safeguard
        await asyncio.sleep(1.0)

    # Build final report
    lines = [
        "🩺 **CDN Health Report**\n",
        f"Total Files Indexed: **{total_files}**",
        f"Verified Active: **{verified_count}**",
    ]
    if legacy_files:
        lines.append(f"Legacy (Unverifiable): **{len(legacy_files)}**")

    if missing_files:
        lines.append(f"\n⚠️ **Detected {len(missing_files)} broken file pointers:**")
        # List up to 20 broken files so message doesn't exceed 4096 characters limit
        for f, path in missing_files[:20]:
            lines.append(f"- 📁 `{path}`/🎬 `{escape_markdown(f.name)}` (ID: `{f.id}`)")
        if len(missing_files) > 20:
            lines.append(f"\n_...and {len(missing_files) - 20} more broken files._")
        lines.append("\n💡 _To fix this, delete these files from database or re-upload them._")
    else:
        lines.append("\n✅ **All active file pointers are verified and operational!**")

    report_text = "\n".join(lines)

    await query.edit_message_text(
        report_text,
        reply_markup=admin_dashboard_kb(),
        parse_mode=ParseMode.MARKDOWN,
    )
