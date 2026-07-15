"""
models/user.py
─────────────────────────────────────────────────────────────────────────────
Beanie Document for RBAC. Three roles:

  OWNER     → Full admin access. Hardcoded to settings.owner_id at first /start.
  APPROVED  → Read-only access — can browse and play videos.
  GUEST     → No access — sees "Access Denied" card with their Telegram ID.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from beanie import Document, PydanticObjectId
from pydantic import Field
from pymongo import IndexModel, ASCENDING


class UserRole(str, Enum):
    OWNER = "owner"
    APPROVED = "approved"
    GUEST = "guest"


class User(Document):
    telegram_id: int                       # Unique Telegram user ID
    role: UserRole = UserRole.GUEST

    # ── Profile (mirrored from Telegram at first contact) ─────────────────────
    full_name: Optional[str] = None
    username: Optional[str] = None         # Without the @ prefix

    # ── Audit trail ───────────────────────────────────────────────────────────
    first_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    approved_at: Optional[datetime] = None
    approved_by: Optional[int] = None      # Telegram ID of approving admin
    revoked_at: Optional[datetime] = None

    # ── UI state (persisted so it survives server restarts) ───────────────────
    last_menu_id: Optional[int] = None     # Telegram message_id of last bot menu
    allowed_folders: list[PydanticObjectId] = Field(default_factory=list)
    blocked_folders: list[PydanticObjectId] = Field(default_factory=list)

    # ── Granular Exception Permissions (Non-Owner write-rights) ───────────────
    can_upload: bool = False
    can_create_folder: bool = False
    can_rename: bool = False
    can_delete: bool = False
    can_move_copy: bool = False

    class Settings:
        name = "users"
        indexes = [
            IndexModel([("telegram_id", ASCENDING)], unique=True),
            # Fast O(1) sort for approved user listings
            IndexModel([("role", ASCENDING), ("full_name", ASCENDING)]),
        ]

    def __repr__(self) -> str:
        return f"<User id={self.telegram_id} role={self.role}>"

    @property
    def display_name(self) -> str:
        """Best available name for UI display."""
        if self.full_name:
            return self.full_name
        if self.username:
            return f"@{self.username}"
        return str(self.telegram_id)
