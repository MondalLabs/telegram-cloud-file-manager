"""
models/user.py
─────────────────────────────────────────────────────────────────────────────
Beanie Document for RBAC. Three roles:

  OWNER     → Full admin access. Hardcoded to settings.owner_id at first /start.
  APPROVED  → Read-only access — can browse and play videos.
  GUEST     → No access — sees "Access Denied" card with their Telegram ID.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from beanie import Document
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
    first_seen: datetime = Field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = None
    approved_by: Optional[int] = None      # Telegram ID of approving admin
    revoked_at: Optional[datetime] = None

    class Settings:
        name = "users"
        indexes = [
            IndexModel([("telegram_id", ASCENDING)], unique=True),
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
