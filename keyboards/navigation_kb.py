"""
keyboards/navigation_kb.py
─────────────────────────────────────────────────────────────────────────────
Builds the main dynamic directory-browsing InlineKeyboardMarkup.

Layout (per page, max 15 combined folder+file items):
  Row 1..N  → Folder buttons  📁 Name
  Row N+1.. → File buttons    🎬 Name  [··meta··]
  ─────────────────────────────────────────────────
  Pagination row (if > 1 page): [◀ Prev]  [2 / 5]  [Next ▶]
  Navigation row: [⬆️ Back]     (admin only: [➕ Folder] [📤 Upload])
  (admin only, on folder/file items): long-press row omitted — use
  separate folder/file action menus via ACTION_FOLDER_INFO / ACTION_FILE_INFO

Callback data byte budget (Safeguard #3):
  nav:{24-char-oid}:{2-digit-page} = 31 bytes ✓
  play:{24-char-oid}               = 29 bytes ✓
  fi:{24-char-oid}                 = 27 bytes ✓
  fli:{24-char-oid}                = 28 bytes ✓
"""

from __future__ import annotations

from typing import Optional

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from models.folder import Folder
from models.file import File
from models.user import User, UserRole
from utils.callback_data import encode, ACTION_NAV, ACTION_PLAY, ACTION_BACK
from utils.callback_data import ACTION_CF, ACTION_UPL, ACTION_FOLDER_INFO, ACTION_FILE_INFO
from utils.pagination import paginate, Page
from bot.config import settings as cfg


def _folder_button(folder: Folder) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=f"📁  {folder.name}",
        callback_data=encode(ACTION_NAV, str(folder.id), 1),
    )


def _file_button(file: File) -> InlineKeyboardButton:
    meta = f"  [{file.display_meta}]" if file.display_meta != "media" else ""
    label = f"{file.icon}  {file.name}{meta}"
    return InlineKeyboardButton(
        text=label,
        callback_data=encode(ACTION_PLAY, str(file.id)),
    )


def _folder_info_button(folder: Folder) -> InlineKeyboardButton:
    """Small ⚙ button next to a folder for admin action menu."""
    return InlineKeyboardButton(
        text="⚙️",
        callback_data=encode(ACTION_FOLDER_INFO, str(folder.id)),
    )


def _file_info_button(file: File) -> InlineKeyboardButton:
    """Small ⚙ button next to a file for admin action menu."""
    return InlineKeyboardButton(
        text="⚙️",
        callback_data=encode(ACTION_FILE_INFO, str(file.id)),
    )


def build_folder_keyboard(
    pg: Page[tuple[str, Folder | File]],
    current_id: str,        # The folder being VIEWED (used for New Folder / Upload / pagination)
    back_id: Optional[str], # The parent folder (used for Back button; None = at root)
    user: User,
) -> InlineKeyboardMarkup:
    """
    Build the paginated directory listing keyboard.

    Args:
        pg:         A Page object containing the slice of folders and files to display.
        current_id: The _id of the folder being viewed ("root" if at root).
        back_id:    The _id of the parent folder (None if already at root).
        user:       The User object requesting the layout (used to dynamically render permissions).
    """
    rows: list[list[InlineKeyboardButton]] = []

    is_owner = user.role == UserRole.OWNER
    can_upload = is_owner or getattr(user, "can_upload", False)
    can_create = is_owner or getattr(user, "can_create_folder", False)
    can_rename = is_owner or getattr(user, "can_rename", False)
    can_delete = is_owner or getattr(user, "can_delete", False)

    # Show the ⚙️ settings button next to folders/files only if user has manage/delete rights
    show_gear = can_rename or can_delete

    for kind, item in pg.items:
        if kind == "folder":
            row = [_folder_button(item)]
            if show_gear:
                row.append(_folder_info_button(item))
        else:
            row = [_file_button(item)]
            if show_gear:
                row.append(_file_info_button(item))
        rows.append(row)

    # ── Pagination row ────────────────────────────────────────────────────────
    if pg.total_pages > 1:
        nav_row: list[InlineKeyboardButton] = []

        if pg.has_prev:
            nav_row.append(InlineKeyboardButton(
                text="◀️",
                callback_data=encode(ACTION_NAV, current_id, pg.prev_page),
            ))
        else:
            nav_row.append(InlineKeyboardButton(text="·", callback_data=encode("noop", "toast", "🚫 No more pages")))

        nav_row.append(InlineKeyboardButton(
            text=f"{pg.page} / {pg.total_pages}",
            callback_data=encode("noop", "toast", f"📄 Page {pg.page} of {pg.total_pages}"),
        ))

        if pg.has_next:
            nav_row.append(InlineKeyboardButton(
                text="▶️",
                callback_data=encode(ACTION_NAV, current_id, pg.next_page),
            ))
        else:
            nav_row.append(InlineKeyboardButton(text="·", callback_data=encode("noop", "toast", "🚫 No more pages")))

        rows.append(nav_row)

    # ── Footer rows ───────────────────────────────────────────────────────────
    footer_row = []
    if can_create:
        footer_row.append(InlineKeyboardButton(
            text="➕ New Folder",
            callback_data=encode(ACTION_CF, current_id),
        ))
    if can_upload:
        footer_row.append(InlineKeyboardButton(
            text="📤 Upload",
            callback_data=encode(ACTION_UPL, current_id),
        ))
    if footer_row:
        rows.append(footer_row)

    nav_row: list[InlineKeyboardButton] = []
    if back_id:
        nav_row.append(InlineKeyboardButton(
            text="⬆️ Back",
            callback_data=encode(ACTION_BACK, back_id),
        ))
    else:
        if is_owner:
            nav_row.append(InlineKeyboardButton(
                text="🛠️ Dashboard",
                callback_data="dashboard",
            ))
        else:
            nav_row.append(InlineKeyboardButton(
                text="🔄 Refresh",
                callback_data="home",
            ))

    rows.append(nav_row)

    return InlineKeyboardMarkup(rows)


def build_empty_folder_keyboard(
    current_id: str,        # The folder being VIEWED
    back_id: Optional[str], # The parent folder (None if at root)
    user: User,
) -> InlineKeyboardMarkup:
    """Keyboard shown when a folder is empty."""
    rows: list[list[InlineKeyboardButton]] = []

    is_owner = user.role == UserRole.OWNER
    can_upload = is_owner or getattr(user, "can_upload", False)
    can_create = is_owner or getattr(user, "can_create_folder", False)

    footer_row = []
    if can_create:
        footer_row.append(InlineKeyboardButton(
            text="➕ New Folder",
            callback_data=encode(ACTION_CF, current_id),
        ))
    if can_upload:
        footer_row.append(InlineKeyboardButton(
            text="📤 Upload",
            callback_data=encode(ACTION_UPL, current_id),
        ))
    if footer_row:
        rows.append(footer_row)

    nav_row: list[InlineKeyboardButton] = []
    if back_id:
        nav_row.append(InlineKeyboardButton(
            text="⬆️ Back",
            callback_data=encode(ACTION_BACK, back_id),
        ))
    else:
        if is_owner:
            nav_row.append(InlineKeyboardButton(
                text="🛠️ Dashboard",
                callback_data="dashboard",
            ))
        else:
            nav_row.append(InlineKeyboardButton(
                text="🔄 Refresh",
                callback_data="home",
            ))

    rows.append(nav_row)

    return InlineKeyboardMarkup(rows)
