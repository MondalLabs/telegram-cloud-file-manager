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
    folders: list[Folder],
    files: list[File],
    page: int,
    current_id: str,        # The folder being VIEWED (used for New Folder / Upload / pagination)
    back_id: Optional[str], # The parent folder (used for Back button; None = at root)
    is_admin: bool,
) -> InlineKeyboardMarkup:
    """
    Build the paginated directory listing keyboard.

    Args:
        folders:    All immediate child folders of the current directory.
        files:      All files in the current directory.
        page:       Current 1-indexed page number.
        current_id: The _id of the folder being viewed ("root" if at root).
        back_id:    The _id of the parent folder (None if already at root).
        is_admin:   Render admin action buttons (⚙️, ➕, 📤) if True.
    """
    combined: list[tuple[str, Folder | File]] = (
        [("folder", f) for f in folders] +
        [("file", f) for f in files]
    )

    pg: Page = paginate(combined, page, cfg.items_per_page)

    rows: list[list[InlineKeyboardButton]] = []

    for kind, item in pg.items:
        if kind == "folder":
            row = [_folder_button(item)]
            if is_admin:
                row.append(_folder_info_button(item))
        else:
            row = [_file_button(item)]
            if is_admin:
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

        nav_row.append(InlineKeyboardButton(
            text=f"{pg.page} / {pg.total_pages}",
            callback_data="noop",
        ))

        if pg.has_next:
            nav_row.append(InlineKeyboardButton(
                text="▶️",
                callback_data=encode(ACTION_NAV, current_id, pg.next_page),
            ))

        rows.append(nav_row)

    # ── Footer row ────────────────────────────────────────────────────────────
    footer: list[InlineKeyboardButton] = []

    if back_id:
        footer.append(InlineKeyboardButton(
            text="⬆️ Back",
            callback_data=encode(ACTION_BACK, back_id),
        ))
    else:
        footer.append(InlineKeyboardButton(
            text="🏠 Home",
            callback_data="home",
        ))

    if is_admin:
        footer.append(InlineKeyboardButton(
            text="➕ New Folder",
            callback_data=encode(ACTION_CF, current_id),
        ))
        footer.append(InlineKeyboardButton(
            text="📤 Upload",
            callback_data=encode(ACTION_UPL, current_id),
        ))

    rows.append(footer)

    return InlineKeyboardMarkup(rows)


def build_empty_folder_keyboard(
    current_id: str,        # The folder being VIEWED
    back_id: Optional[str], # The parent folder (None if at root)
    is_admin: bool,
) -> InlineKeyboardMarkup:
    """Keyboard shown when a folder is empty."""
    footer: list[InlineKeyboardButton] = []

    if back_id:
        footer.append(InlineKeyboardButton(
            text="⬆️ Back",
            callback_data=encode(ACTION_BACK, back_id),
        ))
    else:
        footer.append(InlineKeyboardButton(
            text="🏠 Home",
            callback_data="home",
        ))

    if is_admin:
        footer.append(InlineKeyboardButton(
            text="➕ New Folder",
            callback_data=encode(ACTION_CF, current_id),
        ))
        footer.append(InlineKeyboardButton(
            text="📤 Upload",
            callback_data=encode(ACTION_UPL, current_id),
        ))

    return InlineKeyboardMarkup([footer] if footer else [[]])
