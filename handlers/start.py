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
    return (
        "🔒 **Access Denied**\n\n"
        "This bot is private and by-invitation only.\n\n"
        "Your Telegram ID:\n"
        f"`{telegram_id}`\n\n"
        "Send this ID to the administrator to request access."
    )


@bot.on_message(filters.command("start") & filters.private)
@any_user
async def start_command(client, message: Message, user: User) -> None:
    """Entry point — renders the correct dashboard based on user role."""

    if user.role == UserRole.OWNER:
        await message.reply(
            f"👋 Welcome back, **{user.display_name}**!\n\n"
            "🛠️ **Admin Dashboard** — Cloud File Manager",
            reply_markup=admin_dashboard_kb(),
            parse_mode=ParseMode.MARKDOWN,
        )

    elif user.role == UserRole.APPROVED:
        await message.reply(
            f"👋 Hello, **{user.display_name}**!\n\n"
            "📚 Browse the library below.",
            reply_markup=_approved_kb(),
            parse_mode=ParseMode.MARKDOWN,
        )

    else:  # GUEST
        await message.reply(
            _guest_text(user.telegram_id),
            parse_mode=ParseMode.MARKDOWN,
        )


# ── Callback: return to dashboard from anywhere ───────────────────────────────

@bot.on_callback_query(filters.regex(r"^dashboard$"))
@owner_only
async def dashboard_callback(client, query: CallbackQuery, user: User) -> None:
    """Return to the admin dashboard."""
    await query.answer()
    await query.edit_message_text(
        f"🛠️ **Admin Dashboard** — Cloud File Manager",
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
        "👤 **User Management**\n\nManage access to the Cloud File Manager.",
        reply_markup=user_management_kb(),
        parse_mode=ParseMode.MARKDOWN,
    )
