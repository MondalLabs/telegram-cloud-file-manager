"""
keyboards/confirm_kb.py
─────────────────────────────────────────────────────────────────────────────
Reusable Yes / No confirmation keyboards for destructive operations.

The "Yes" button encodes the original action + target so the confirm handler
knows exactly what to execute without requiring FSM state.

Callback data format: "yes:{original_action}:{target_id}"
  e.g. "yes:df:6a08ce62ae36ee491a35cd99"  → delete folder
       "yes:delf:6a08ce62ae36ee491a35cd99" → delete file
"""

from __future__ import annotations

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from utils.callback_data import encode, ACTION_CONFIRM, ACTION_CANCEL


def confirm_delete_kb(
    action: str,
    target_id: str,
    label: str = "Delete",
) -> InlineKeyboardMarkup:
    """
    Generic Yes/No confirmation keyboard.

    Args:
        action:    The action prefix that will execute on confirm
                   (e.g. ACTION_DF for delete-folder).
        target_id: The MongoDB document ID string of the target.
        label:     Text shown on the confirm button (default: "Delete").
    """
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                text=f"✅ Yes, {label}",
                callback_data=encode(ACTION_CONFIRM, action, target_id),
            ),
            InlineKeyboardButton(
                text="❌ Cancel",
                callback_data=encode(ACTION_CANCEL),
            ),
        ],
    ])


def confirm_revoke_kb(user_doc_id: str, display_name: str) -> InlineKeyboardMarkup:
    """
    Specific confirm keyboard for revoking a user's access.
    Button encodes yes:ur:{id} so it hits the revoke_confirmed handler,
    NOT the show-confirmation handler (which would cause an infinite loop).
    """
    from utils.callback_data import ACTION_USR_REVOKE, ACTION_CONFIRM
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                text=f"✅ Revoke {display_name}",
                callback_data=encode(ACTION_CONFIRM, ACTION_USR_REVOKE, user_doc_id),
            ),
            InlineKeyboardButton(
                text="❌ Cancel",
                callback_data=encode(ACTION_CANCEL),
            ),
        ],
    ])
