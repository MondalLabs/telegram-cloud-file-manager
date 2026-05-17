"""
keyboards/admin_kb.py
─────────────────────────────────────────────────────────────────────────────
Admin-specific keyboard builders:
  • admin_dashboard_kb()        — main menu shown on /start (Owner only)
  • folder_actions_kb()         — per-folder action menu (Rename / Delete / Upload)
  • file_actions_kb()           — per-file action menu   (Rename / Delete)
  • user_management_kb()        — user management sub-menu
  • upload_cancel_kb()          — shown during active upload session
"""

from __future__ import annotations

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from utils.callback_data import (
    encode,
    ACTION_NAV,
    ACTION_RF, ACTION_DF,
    ACTION_REN_FILE, ACTION_DEL_FILE,
    ACTION_UPL,
    ACTION_USR_APPROVE, ACTION_USR_LIST,
    ACTION_CANCEL,
)


def admin_dashboard_kb() -> InlineKeyboardMarkup:
    """Main admin control panel shown on /start."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                text="📂 Browse Files",
                callback_data=encode(ACTION_NAV, "root", 1),
            ),
        ],
        [
            InlineKeyboardButton(
                text="👤 Manage Users",
                callback_data="usrmenu",
            ),
        ],
    ])


def folder_actions_kb(folder_id: str, parent_id: str | None) -> InlineKeyboardMarkup:
    """
    Action menu for a specific folder.
    Triggered by the ⚙️ button next to a folder in the listing.
    """
    back_cb = encode(ACTION_NAV, parent_id or "root", 1)
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                text="✏️ Rename",
                callback_data=encode(ACTION_RF, folder_id),
            ),
            InlineKeyboardButton(
                text="📤 Upload Here",
                callback_data=encode(ACTION_UPL, folder_id),
            ),
        ],
        [
            InlineKeyboardButton(
                text="🗑️ Delete Folder",
                callback_data=encode(ACTION_DF, folder_id),
            ),
        ],
        [
            InlineKeyboardButton(
                text="⬅️ Back to Listing",
                callback_data=back_cb,
            ),
        ],
    ])


def file_actions_kb(file_id: str, folder_id: str) -> InlineKeyboardMarkup:
    """
    Action menu for a specific file.
    Triggered by the ⚙️ button next to a file in the listing.
    """
    back_cb = encode(ACTION_NAV, folder_id, 1)
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                text="✏️ Rename",
                callback_data=encode(ACTION_REN_FILE, file_id),
            ),
            InlineKeyboardButton(
                text="🗑️ Delete",
                callback_data=encode(ACTION_DEL_FILE, file_id),
            ),
        ],
        [
            InlineKeyboardButton(
                text="⬅️ Back to Listing",
                callback_data=back_cb,
            ),
        ],
    ])


def user_management_kb() -> InlineKeyboardMarkup:
    """User management sub-menu."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                text="✅ Approve User",
                callback_data=encode(ACTION_USR_APPROVE),
            ),
        ],
        [
            InlineKeyboardButton(
                text="📋 View Approved",
                callback_data=encode(ACTION_USR_LIST, 1),
            ),
        ],
        [
            InlineKeyboardButton(
                text="⬅️ Back to Dashboard",
                callback_data="dashboard",
            ),
        ],
    ])


def upload_cancel_kb() -> InlineKeyboardMarkup:
    """Shown during an active upload session so admin can abort."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                text="✅ Done Uploading",
                callback_data="upload_done",
            ),
            InlineKeyboardButton(
                text="❌ Cancel Upload",
                callback_data=encode(ACTION_CANCEL),
            ),
        ],
    ])
