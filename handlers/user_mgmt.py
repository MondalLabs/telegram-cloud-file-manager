"""
handlers/user_mgmt.py
─────────────────────────────────────────────────────────────────────────────
User management for the Owner — approve, revoke, and list users.

FSM state: "approve_user:waiting_id"
  data: {}   (no context needed — just waiting for the Telegram ID)

Callback patterns:
  ua         — start Approve User FSM
  ul:{page}  — list approved users (paginated)
  ur:{user_doc_id}  — confirm revocation (then execute)

The revoke action is handled statelessly — user is selected from the
paginated list (each row is a button with user_doc_id in callback_data),
then confirmed with confirm_revoke_kb(), then executed.
"""

from __future__ import annotations
from utils.sanitize import escape_markdown

import logging

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message, CallbackQuery
from beanie import PydanticObjectId

from bot.client import bot
from models.user import User, UserRole
from models.folder import Folder
from middlewares.access_control import owner_only
from keyboards.admin_kb import user_management_kb
from keyboards.confirm_kb import confirm_revoke_kb, cancel_only_kb
import services.user_service as user_service
import services.fsm_service as fsm_service
from utils.callback_data import decode, encode, ACTION_USR_LIST, ACTION_USR_REVOKE
from utils.pagination import Page
from bot.config import settings as cfg
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

log = logging.getLogger(__name__)

# ── Approve User FSM ──────────────────────────────────────────────────────────

@bot.on_callback_query(filters.regex(r"^ua$"))
@owner_only
async def approve_start(client, query: CallbackQuery, user: User) -> None:
    """Start the Approve User FSM: ask for a Telegram ID."""
    await query.answer()
    await fsm_service.set_state(
        user.telegram_id,
        state="approve_user:waiting_id",
        data={"from_menu": "usrmenu"},
    )
    await query.edit_message_text(
        "✅ **Approve User**\n\n"
        "Send the Telegram ID of the user you want to approve.\n"
        "Or tap Cancel to abort.",
        reply_markup=cancel_only_kb(),
        parse_mode=ParseMode.MARKDOWN,
    )

@bot.on_message(filters.text & filters.private & ~filters.command(["start", "cancel", "done"]), group=1)
@owner_only
async def approve_user_id_input(client, message: Message, user: User) -> None:
    """
    Process the Telegram ID input for the Approve User FSM.
    Registered in group=1 so it fires AFTER fsm_text_router (group=0) in
    admin_crud.py. Pyrogram only fires the first matching handler per group,
    so without the different group this handler would never be called.
    """
    state, data = await fsm_service.get_state_and_data(user.telegram_id)
    if state != "approve_user:waiting_id":
        return  # Not our FSM state — let admin_crud handle it

    raw = message.text.strip()
    try:
        target_id = int(raw)
    except ValueError:
        await message.reply(
            "⚠️ That doesn't look like a valid Telegram ID. Send a number.\n\nOr tap Cancel to abort.",
            reply_markup=cancel_only_kb()
        )
        return

    if target_id == cfg.owner_id:
        await message.reply(
            "⚠️ You can't approve/modify the owner account.\n\nOr tap Cancel to abort.",
            reply_markup=cancel_only_kb()
        )
        return

    # ── Validate: user must have messaged the bot first ────────────────────────
    existing = await user_service.find_user_by_id(target_id)
    if existing is None:
        await message.reply(
            f"⚠️ **User not found**\n\n"
            f"No user with ID `{target_id}` has ever messaged this bot.\n"
            f"They must send /start to the bot first before you can approve them.\n\n"
            f"Or tap Cancel to abort.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=cancel_only_kb()
        )
        return

    try:
        approved = await user_service.approve_user(target_id, approved_by=user.telegram_id)
    except ValueError as e:
        log.error("Approve user error: %s", e)
        await message.reply(
            "⚠️ Failed to approve user.\n\nOr tap Cancel to abort.",
            reply_markup=cancel_only_kb()
        )
        return

    await fsm_service.clear_state(user.telegram_id)

    await message.reply(
        f"✅ **Access Granted**\n\n"
        f"User **{escape_markdown(approved.display_name)}** (`{target_id}`) "
        f"has been approved and can now browse the library.",
        reply_markup=user_management_kb(),
        parse_mode=ParseMode.MARKDOWN,
    )

# ── List Approved Users (paginated) ──────────────────────────────────────────

@bot.on_callback_query(filters.regex(r"^ul:"))
@owner_only
async def list_approved_users(client, query: CallbackQuery, user: User) -> None:
    """Show a paginated list of all approved users."""
    await query.answer()
    parts = decode(query.data)
    page = int(parts[1]) if len(parts) > 1 else 1

    total_items = await user_service.count_approved()

    if total_items == 0:
        await query.edit_message_text(
            "📋 **Approved Users**\n\nNo approved users yet.\nTap ✅ Approve User to grant access.",
            reply_markup=user_management_kb(),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    per_page = cfg.items_per_page
    total_pages = max(1, (total_items + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))

    start = (page - 1) * per_page

    page_users = await user_service.get_approved_paginated(start, per_page)

    pg = Page(
        items=page_users,
        page=page,
        total_pages=total_pages,
        total_items=total_items,
    )

    # Build user list rows — each user is a button that opens their detailed profile view
    rows = []
    for u in pg.items:
        name = u.display_name
        rows.append([
            InlineKeyboardButton(
                text=f"👤 {name} ({u.telegram_id})",
                callback_data=encode("udetail", str(u.id)),
            )
        ])

    # Pagination row
    if pg.total_pages > 1:
        nav = []
        if pg.has_prev:
            nav.append(InlineKeyboardButton(
                text="◀️", callback_data=encode(ACTION_USR_LIST, pg.prev_page)
            ))
        else:
            nav.append(InlineKeyboardButton(text="·", callback_data=encode("noop", "toast", "🚫 No more pages")))
        nav.append(InlineKeyboardButton(
            text=f"{pg.page}/{pg.total_pages}", callback_data=encode("noop", "toast", f"📄 Page {pg.page} of {pg.total_pages}")
        ))
        if pg.has_next:
            nav.append(InlineKeyboardButton(
                text="▶️", callback_data=encode(ACTION_USR_LIST, pg.next_page)
            ))
        else:
            nav.append(InlineKeyboardButton(text="·", callback_data=encode("noop", "toast", "🚫 No more pages")))
        rows.append(nav)

    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="usrmenu")])

    await query.edit_message_text(
        f"📋 **Approved Users** ({pg.total_items} total)\n\n"
        f"Tap a user to view their profile and manage folder exceptions.",
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode=ParseMode.MARKDOWN,
    )

# ── Revoke User ───────────────────────────────────────────────────────────────

@bot.on_callback_query(filters.regex(r"^ur:"))
@owner_only
async def revoke_user_callback(client, query: CallbackQuery, user: User) -> None:
    """
    First tap: show confirmation keyboard.
    Uses confirm_revoke_kb which re-encodes ur:{user_doc_id} — when the
    confirm button is tapped, this same handler runs again but now we detect
    it's a confirmed action because query.data starts with "ur:" followed by
    a user doc ID, and the confirm_revoke_kb sends "ur:{id}" directly.
    
    Actually, we use a two-step: first tap shows confirm, confirm tap executes.
    We distinguish by checking if FSM has a "revoke_confirm:{id}" state.
    Simpler: use the confirm keyboard's "yes" button with action=ur.
    """
    await query.answer()
    parts = decode(query.data)
    user_doc_id = parts[1]

    target = await user_service.find_user_by_id_doc(user_doc_id)
    if target is None:
        await query.answer("❌ User not found.", show_alert=True)
        return

    cancel_data = encode(ACTION_USR_LIST, 1)

    try:
        await query.edit_message_text(
            f"🚫 **Revoke Access**\n\n"
            f"User: **{escape_markdown(target.display_name)}**\n"
            f"ID: `{target.telegram_id}`\n\n"
            f"This user will no longer be able to browse the library.",
            reply_markup=confirm_revoke_kb(user_doc_id, target.display_name, cancel_data=cancel_data),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        if "MESSAGE_NOT_MODIFIED" in str(e):
            pass  # Confirmation already showing — safe to ignore
        else:
            raise

# Register the yes:ur: confirmation in confirm_kb — handled by admin_crud.py's
# general yes: handler. But for revoke we need custom logic, so we handle it here.

@bot.on_callback_query(filters.regex(r"^yes:ur:"))
@owner_only
async def revoke_confirmed(client, query: CallbackQuery, user: User) -> None:
    """Execute the confirmed user revocation."""
    await query.answer()
    parts = decode(query.data)
    user_doc_id = parts[2]

    target = await user_service.find_user_by_id_doc(user_doc_id)
    if target is None:
        await query.edit_message_text("❌ User not found.", reply_markup=user_management_kb())
        return

    await user_service.revoke_user(target.telegram_id)

    await query.edit_message_text(
        f"✅ **Access Revoked**\n\n"
        f"**{escape_markdown(target.display_name)}** (`{target.telegram_id}`) "
        f"has been downgraded to Guest.",
        reply_markup=user_management_kb(),
        parse_mode=ParseMode.MARKDOWN,
    )


# ── User Details Exception View ───────────────────────────────────────────────

@bot.on_callback_query(filters.regex(r"^udetail:"))
@owner_only
async def user_detail_callback(client, query: CallbackQuery, user: User) -> None:
    await query.answer()
    parts = decode(query.data)
    user_doc_id = parts[1]

    target = await user_service.find_user_by_id_doc(user_doc_id)
    if target is None:
        await query.answer("❌ User not found.", show_alert=True)
        return

    # Build allowed/blocked folders names lists
    allowed_names = []
    for fid in target.allowed_folders:
        folder = await Folder.get(fid)
        if folder:
            allowed_names.append(folder.name)

    blocked_names = []
    for fid in target.blocked_folders:
        folder = await Folder.get(fid)
        if folder:
            blocked_names.append(folder.name)

    allowed_str = ", ".join(allowed_names) if allowed_names else "All folders (Default)"
    blocked_str = ", ".join(blocked_names) if blocked_names else "None"

    since = target.approved_at.strftime("%Y-%m-%d") if target.approved_at else "unknown"

    text = (
        f"👤 **User Profile**\n\n"
        f"Name: **{escape_markdown(target.display_name)}**\n"
        f"Telegram ID: `{target.telegram_id}`\n"
        f"Approved on: `{since}`\n\n"
        f"🟢 **Allowed Exceptions**:\n"
        f"_{escape_markdown(allowed_str)}_\n\n"
        f"🔴 **Blocked Exceptions**:\n"
        f"_{escape_markdown(blocked_str)}_\n\n"
        f"💡 _Exceptions apply recursively to subfolders._"
    )

    buttons = [
        [
            InlineKeyboardButton("🟢 Allow Folder", callback_data=encode("uallow", user_doc_id, 1)),
            InlineKeyboardButton("🔴 Block Folder", callback_data=encode("ublock", user_doc_id, 1)),
        ],
        [
            InlineKeyboardButton("⚪ Reset Permissions", callback_data=encode("ureset", user_doc_id)),
        ],
        [
            InlineKeyboardButton("🚫 Revoke Access", callback_data=encode(ACTION_USR_REVOKE, user_doc_id)),
        ],
        [
            InlineKeyboardButton("⬅️ Back to List", callback_data=encode(ACTION_USR_LIST, 1)),
        ]
    ]

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.MARKDOWN,
    )


@bot.on_callback_query(filters.regex(r"^ureset:"))
@owner_only
async def user_reset_permissions_callback(client, query: CallbackQuery, user: User) -> None:
    parts = decode(query.data)
    user_doc_id = parts[1]

    target = await user_service.find_user_by_id_doc(user_doc_id)
    if target is None:
        await query.answer("❌ User not found.", show_alert=True)
        return

    await user_service.reset_folder_permissions_for_user(target)
    await query.answer("✅ Permissions reset successfully.")

    # Redirect to user details view
    query.data = encode("udetail", user_doc_id)
    await user_detail_callback(client, query, user)


@bot.on_callback_query(filters.regex(r"^(uallow|ublock):"))
@owner_only
async def user_folder_select_callback(client, query: CallbackQuery, user: User) -> None:
    await query.answer()
    parts = decode(query.data)
    action = parts[0]  # "uallow" or "ublock"
    user_doc_id = parts[1]
    page = int(parts[2]) if len(parts) > 2 else 1

    target = await user_service.find_user_by_id_doc(user_doc_id)
    if target is None:
        await query.answer("❌ User not found.", show_alert=True)
        return

    folders = await Folder.find_all().sort(+Folder.name).to_list()

    if not folders:
        await query.answer("⚠️ No virtual folders exist yet.", show_alert=True)
        return

    total_items = len(folders)
    per_page = cfg.items_per_page
    total_pages = max(1, (total_items + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))

    start = (page - 1) * per_page
    end = start + per_page
    page_folders = folders[start:end]

    pg = Page(
        items=page_folders,
        page=page,
        total_pages=total_pages,
        total_items=total_items,
    )

    rows = []
    mode_str = "Allow" if action == "uallow" else "Block"
    color_emoji = "🟢" if action == "uallow" else "🔴"

    for f in pg.items:
        exists = f.id in (target.allowed_folders if action == "uallow" else target.blocked_folders)
        indicator = "  [Active]" if exists else ""
        rows.append([
            InlineKeyboardButton(
                text=f"{f.name}{indicator}",
                callback_data=encode("addexc", action, user_doc_id, str(f.id)),
            )
        ])

    if pg.total_pages > 1:
        nav = []
        if pg.has_prev:
            nav.append(InlineKeyboardButton("◀️", callback_data=encode(action, user_doc_id, pg.prev_page)))
        else:
            nav.append(InlineKeyboardButton("·", callback_data=encode("noop", "toast", "🚫 No more pages")))
        nav.append(InlineKeyboardButton(f"{pg.page}/{pg.total_pages}", callback_data=encode("noop", "toast", f"📄 Page {pg.page} of {pg.total_pages}")))
        if pg.has_next:
            nav.append(InlineKeyboardButton("▶️", callback_data=encode(action, user_doc_id, pg.next_page)))
        else:
            nav.append(InlineKeyboardButton("·", callback_data=encode("noop", "toast", "🚫 No more pages")))
        rows.append(nav)

    rows.append([InlineKeyboardButton("⬅️ Back to Profile", callback_data=encode("udetail", user_doc_id))])

    await query.edit_message_text(
        f"{color_emoji} **Select Folder to {mode_str}**\n\n"
        f"Select a virtual folder to toggle as an exception for **{escape_markdown(target.display_name)}**.",
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode=ParseMode.MARKDOWN,
    )


@bot.on_callback_query(filters.regex(r"^addexc:"))
@owner_only
async def toggle_exception_callback(client, query: CallbackQuery, user: User) -> None:
    parts = decode(query.data)
    action = parts[1]  # "uallow" or "ublock"
    user_doc_id = parts[2]
    folder_id_str = parts[3]

    target = await user_service.find_user_by_id_doc(user_doc_id)
    if target is None:
        await query.answer("❌ User not found.", show_alert=True)
        return

    # Security Enhancement: Validate user input from callback query to prevent unhandled InvalidId exceptions
    if not PydanticObjectId.is_valid(folder_id_str):
        await query.answer("❌ Invalid folder ID.", show_alert=True)
        return

    folder_id = PydanticObjectId(folder_id_str)

    if action == "uallow":
        if folder_id in target.allowed_folders:
            target.allowed_folders.remove(folder_id)
            await target.save()
            await query.answer("Removed from allowed exceptions.")
        else:
            await user_service.allow_folder_for_user(target, folder_id)
            await query.answer("Added to allowed exceptions.")
    else:
        if folder_id in target.blocked_folders:
            target.blocked_folders.remove(folder_id)
            await target.save()
            await query.answer("Removed from blocked exceptions.")
        else:
            await user_service.block_folder_for_user(target, folder_id)
            await query.answer("Added to blocked exceptions.")

    # Refresh folder select list
    query.data = encode(action, user_doc_id, 1)
    await user_folder_select_callback(client, query, user)
