"""
middlewares/access_control.py
─────────────────────────────────────────────────────────────────────────────
Role-Based Access Control (RBAC) gate for all Pyrofork handlers.

Usage — decorate any handler with @require_role():

    @bot.on_message(filters.command("start"))
    @require_role(UserRole.OWNER, UserRole.APPROVED, UserRole.GUEST)
    async def start_handler(client, message, user: User):
        ...

    @bot.on_callback_query(filters.regex(r"^cf:"))
    @require_role(UserRole.OWNER)
    async def create_folder_cb(client, query, user: User):
        ...

The decorator:
  1. Calls user_service.get_or_create() — auto-creates guest records and
     auto-promotes the owner. This is the single, authoritative user-touch
     point for every incoming update.
  2. Checks if the user's role is in allowed_roles.
  3. If not allowed — sends the appropriate denial message and returns early.
  4. If allowed — injects the resolved User object as a keyword arg (user=).

Supported update types: Message, CallbackQuery.
"""

from __future__ import annotations

import logging
from functools import wraps
from typing import Callable

from pyrogram.enums import ParseMode
from pyrogram.types import Message, CallbackQuery

from models.user import User, UserRole
import services.user_service as user_service

log = logging.getLogger(__name__)


def _extract_from_user(update: Message | CallbackQuery):
    """Extract the Telegram from_user object from either update type."""
    if isinstance(update, CallbackQuery):
        return update.from_user
    return update.from_user  # same attribute name on Message


async def _send_denial(update: Message | CallbackQuery, user: User) -> None:
    """Send the appropriate access-denied message for the user's context."""
    if user.role == UserRole.GUEST:
        text = (
            "🔒 **Access Denied**\n\n"
            "This bot is private. Your Telegram ID is:\n"
            f"`{user.telegram_id}`\n\n"
            "Send this ID to the administrator to request access."
        )
    else:
        text = "⛔ **Permission Denied** — this action requires administrator access."

    if isinstance(update, CallbackQuery):
        await update.answer(text="⛔ Access denied.", show_alert=True)
        # Also send a chat message for guest denials so they see the ID
        if user.role == UserRole.GUEST:
            await update.message.reply(text, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.reply(text, parse_mode=ParseMode.MARKDOWN)


def require_role(*allowed_roles: UserRole) -> Callable:
    """
    Decorator factory that gates a handler by the caller's RBAC role.

    Args:
        *allowed_roles: One or more UserRole values permitted to execute
                        the decorated handler.

    The resolved User object is injected as 'user=...' into the handler's
    keyword arguments.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(client, update: Message | CallbackQuery, *args, **kwargs):
            from_user = _extract_from_user(update)
            if from_user is None:
                log.warning("Received update with no from_user — ignoring.")
                return

            user = await user_service.get_or_create(
                telegram_id=from_user.id,
                full_name=from_user.first_name,
                username=from_user.username,
            )

            if user.role not in allowed_roles:
                await _send_denial(update, user)
                return

            return await func(client, update, *args, user=user, **kwargs)

        return wrapper
    return decorator


# ── Convenience aliases ───────────────────────────────────────────────────────

def owner_only(func: Callable) -> Callable:
    """Shorthand: @owner_only — only OWNER may execute."""
    return require_role(UserRole.OWNER)(func)


def approved_and_above(func: Callable) -> Callable:
    """Shorthand: @approved_and_above — OWNER and APPROVED may execute."""
    return require_role(UserRole.OWNER, UserRole.APPROVED)(func)


def any_user(func: Callable) -> Callable:
    """Shorthand: @any_user — all roles including GUEST may execute."""
    return require_role(UserRole.OWNER, UserRole.APPROVED, UserRole.GUEST)(func)
