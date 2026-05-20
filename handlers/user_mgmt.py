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
from middlewares.access_control import owner_only
from keyboards.admin_kb import user_management_kb, admin_dashboard_kb
from keyboards.confirm_kb import confirm_revoke_kb, cancel_only_kb
import services.user_service as user_service
import services.fsm_service as fsm_service
from utils.callback_data import decode, encode, ACTION_USR_LIST, ACTION_USR_REVOKE
from utils.pagination import paginate
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
        await message.reply("⚠️ That doesn't look like a valid Telegram ID. Send a number.")
        return

    if target_id == cfg.owner_id:
        await message.reply("⚠️ You can't approve/modify the owner account.")
        return

    # ── Validate: user must have messaged the bot first ────────────────────────
    existing = await user_service.find_user_by_id(target_id)
    if existing is None:
        await message.reply(
            f"⚠️ **User not found**\n\n"
            f"No user with ID `{target_id}` has ever messaged this bot.\n"
            f"They must send /start to the bot first before you can approve them.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    try:
        approved = await user_service.approve_user(target_id, approved_by=user.telegram_id)
    except ValueError as e:
        await message.reply(f"⚠️ {e}")
        await fsm_service.clear_state(user.telegram_id)
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

    approved = await user_service.list_approved()

    if not approved:
        await query.edit_message_text(
            "📋 **Approved Users**\n\nNo approved users yet.\nTap ✅ Approve User to grant access.",
            reply_markup=user_management_kb(),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    pg = paginate(approved, page, cfg.items_per_page)

    # Build user list rows — each user gets a Revoke button
    rows = []
    for u in pg.items:
        name = u.display_name
        since = u.approved_at.strftime("%Y-%m-%d") if u.approved_at else "unknown"
        rows.append([
            InlineKeyboardButton(
                text=f"👤 {name} ({u.telegram_id})",
                callback_data="noop",
            ),
            InlineKeyboardButton(
                text="🚫 Revoke",
                callback_data=encode(ACTION_USR_REVOKE, str(u.id)),
            ),
        ])

    # Pagination row
    if pg.total_pages > 1:
        nav = []
        if pg.has_prev:
            nav.append(InlineKeyboardButton(
                text="◀️", callback_data=encode(ACTION_USR_LIST, pg.prev_page)
            ))
        nav.append(InlineKeyboardButton(
            text=f"{pg.page}/{pg.total_pages}", callback_data="noop"
        ))
        if pg.has_next:
            nav.append(InlineKeyboardButton(
                text="▶️", callback_data=encode(ACTION_USR_LIST, pg.next_page)
            ))
        rows.append(nav)

    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="usrmenu")])

    await query.edit_message_text(
        f"📋 **Approved Users** ({pg.total_items} total)\n\n"
        f"Tap 🚫 Revoke to remove access from a user.",
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

    try:
        await query.edit_message_text(
            f"🚫 **Revoke Access**\n\n"
            f"User: **{escape_markdown(target.display_name)}**\n"
            f"ID: `{target.telegram_id}`\n\n"
            f"This user will no longer be able to browse the library.",
            reply_markup=confirm_revoke_kb(user_doc_id, target.display_name),
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
