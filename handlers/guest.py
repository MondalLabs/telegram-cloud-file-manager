"""
handlers/guest.py
─────────────────────────────────────────────────────────────────────────────
Catch-all handler for GUEST users who try to interact with the bot.

Priority: This handler MUST be registered LAST in __main__.py (or have
the lowest handler priority) so it doesn't intercept messages meant for
other handlers. It only fires when the user's role is GUEST.

Shows the user their Telegram ID so they can send it to the administrator
for access approval.
"""

from __future__ import annotations

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message, CallbackQuery

from bot.client import bot
from models.user import UserRole
import services.user_service as user_service

def _access_denied_text(telegram_id: int) -> str:
    return (
        "🔒 **Access Denied**\n\n"
        "This bot is private and requires approval.\n\n"
        "Your Telegram ID:\n"
        f"`{telegram_id}`\n\n"
        "Send this ID to the administrator to request access."
    )

@bot.on_message(filters.private & ~filters.command(["start", "cancel", "done"]))
async def guest_message_handler(client, message: Message) -> None:
    """
    Intercepts any private message from a GUEST or unknown user.
    Registered as a low-priority handler — role-specific handlers
    run first via their @require_role decorators.
    """
    if message.from_user is None:
        return

    user = await user_service.get_or_create(
        telegram_id=message.from_user.id,
        full_name=message.from_user.first_name,
        username=message.from_user.username,
    )

    if user.role == UserRole.GUEST:
        await message.reply(
            _access_denied_text(user.telegram_id),
            parse_mode=ParseMode.MARKDOWN,
        )

@bot.on_callback_query(filters.regex(r"^guest_"))
async def guest_callback_handler(client, query: CallbackQuery) -> None:
    """Handles any stale callback buttons that guests might tap."""
    if query.from_user is None:
        return
    await query.answer(
        "🔒 Access denied. Contact the administrator.",
        show_alert=True,
    )
