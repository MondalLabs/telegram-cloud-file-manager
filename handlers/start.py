"""
handlers/start.py
─────────────────────────────────────────────────────────────────────────────
/start command — Role-based entry point.

  OWNER    → Admin dashboard with Browse + Manage Users buttons
  APPROVED → Browse Library button only
  GUEST    → Access denied card showing their Telegram ID

Also handles the "dashboard" and "home" callback queries to return the
user to the main menu from anywhere in the navigation tree.
"""

from __future__ import annotations

import logging

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot.client import bot
from bot.config import settings as cfg
from models.user import User, UserRole
from middlewares.access_control import any_user, owner_only
from keyboards.admin_kb import admin_dashboard_kb, user_management_kb
from utils.callback_data import encode, ACTION_NAV

log = logging.getLogger(__name__)


def _approved_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            text="📂 Browse Library",
            callback_data=encode(ACTION_NAV, "root", 1),
        )
    ]])


def _guest_text(telegram_id: int) -> str:
    name_clause = f" to **{cfg.display_name}**" if cfg.display_name else ""
    return (
        "🔒 **Access Denied**\n\n"
        f"This bot is private and by-invitation only.\n\n"
        "Your Telegram ID:\n"
        f"`{telegram_id}`\n\n"
        f"Send this ID to the administrator to request access{name_clause}."
    )


@bot.on_message(filters.command("start") & filters.private)
@any_user
async def start_command(client, message: Message, user: User) -> None:
    """Entry point — renders the correct dashboard based on user role."""

    # Delete the previous menu message to keep the chat clean
    if user.last_menu_id:
        try:
            await client.delete_messages(message.chat.id, user.last_menu_id)
        except Exception:
            pass  # Already deleted, too old (>48h), or message not found

    if user.role == UserRole.OWNER:
        name_line = f" — **{cfg.display_name}**" if cfg.display_name else ""
        sent = await message.reply(
            f"👋 Welcome back, **{user.display_name}**!\n\n"
            f"🛠️ **Admin Dashboard**{name_line}",
            reply_markup=admin_dashboard_kb(),
            parse_mode=ParseMode.MARKDOWN,
        )

    elif user.role == UserRole.APPROVED:
        name_line = f" to **{cfg.display_name}**" if cfg.display_name else ""
        sent = await message.reply(
            f"👋 Hello, **{user.display_name}**! Welcome{name_line}.\n\n"
            "📚 Browse the library below.",
            reply_markup=_approved_kb(),
            parse_mode=ParseMode.MARKDOWN,
        )

    else:  # GUEST — no menu to track (they have no navigation)
        await message.reply(
            _guest_text(user.telegram_id),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Persist the new menu message ID so it survives server restarts
    await user.set({User.last_menu_id: sent.id})


# ── Callback: return to dashboard from anywhere ───────────────────────────────

@bot.on_callback_query(filters.regex(r"^dashboard$"))
@owner_only
async def dashboard_callback(client, query: CallbackQuery, user: User) -> None:
    """Return to the admin dashboard."""
    await query.answer()
    await query.edit_message_text(
        f"🛠️ **Admin Dashboard**",
        reply_markup=admin_dashboard_kb(),
        parse_mode=ParseMode.MARKDOWN,
    )


@bot.on_callback_query(filters.regex(r"^home$"))
@any_user
async def home_callback(client, query: CallbackQuery, user: User) -> None:
    """Return to the user's home view (root folder listing)."""
    await query.answer()
    # Re-trigger navigation to root — import here to avoid circular imports
    from handlers.navigation import render_folder
    await render_folder(client, query, folder_id=None, page=1, user=user)


@bot.on_callback_query(filters.regex(r"^usrmenu$"))
@owner_only
async def user_menu_callback(client, query: CallbackQuery, user: User) -> None:
    """Open the user management sub-menu."""
    await query.answer()
    await query.edit_message_text(
        "👤 **User Management**\n\nManage user access to the library.",
        reply_markup=user_management_kb(),
        parse_mode=ParseMode.MARKDOWN,
    )
