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
from models.user import User, UserRole

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
        [
            InlineKeyboardButton(
                text="🩺 Run Health Check",
                callback_data="healthcheck",
            ),
        ],
    ])


def folder_actions_kb(folder_id: str, parent_id: str | None, user: User) -> InlineKeyboardMarkup:
    """
    Action menu for a specific folder.
    Triggered by the ⚙️ button next to a folder in the listing.
    """
    is_owner = user.role == UserRole.OWNER
    can_rename = is_owner or getattr(user, "can_rename", False)
    can_upload = is_owner or getattr(user, "can_upload", False)
    can_delete = is_owner or getattr(user, "can_delete", False)

    back_cb = encode(ACTION_NAV, parent_id or "root", 1)
    
    top_row = []
    if can_rename:
        top_row.append(InlineKeyboardButton(
            text="✏️ Rename",
            callback_data=encode(ACTION_RF, folder_id),
        ))
    if can_upload:
        top_row.append(InlineKeyboardButton(
            text="📤 Upload Here",
            callback_data=encode(ACTION_UPL, folder_id),
        ))

    rows = []
    if top_row:
        rows.append(top_row)
        
    if can_delete:
        rows.append([
            InlineKeyboardButton(
                text="🗑️ Delete Folder",
                callback_data=encode(ACTION_DF, folder_id),
            ),
        ])

    rows.append([
        InlineKeyboardButton(
            text="⬅️ Back to Listing",
            callback_data=back_cb,
        ),
    ])

    return InlineKeyboardMarkup(rows)


def file_actions_kb(file_id: str, folder_id: str, user: User) -> InlineKeyboardMarkup:
    """
    Action menu for a specific file.
    Triggered by the ⚙️ button next to a file in the listing.
    """
    is_owner = user.role == UserRole.OWNER
    can_rename = is_owner or getattr(user, "can_rename", False)
    can_delete = is_owner or getattr(user, "can_delete", False)

    back_cb = encode(ACTION_NAV, folder_id, 1)
    
    action_row = []
    if can_rename:
        action_row.append(InlineKeyboardButton(
            text="✏️ Rename",
            callback_data=encode(ACTION_REN_FILE, file_id),
        ))
    if can_delete:
        action_row.append(InlineKeyboardButton(
            text="🗑️ Delete",
            callback_data=encode(ACTION_DEL_FILE, file_id),
        ))

    rows = []
    if action_row:
        rows.append(action_row)
        
    rows.append([
        InlineKeyboardButton(
            text="⬅️ Back to Listing",
            callback_data=back_cb,
        ),
    ])

    return InlineKeyboardMarkup(rows)


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
