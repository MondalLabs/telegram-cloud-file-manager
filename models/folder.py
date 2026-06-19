"""
models/folder.py
─────────────────────────────────────────────────────────────────────────────
Beanie Document representing a directory node in the adjacency-list tree.

Design:
  • parent_id = None  → root-level folder
  • parent_id = <id>  → child of that folder
  • Unique compound index on (name, parent_id) prevents duplicate sibling names.
  • Index on parent_id alone gives O(1) children lookups.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from beanie import Document, PydanticObjectId
from pydantic import Field
from pymongo import IndexModel, ASCENDING


class Folder(Document):
    name: str
    parent_id: Optional[PydanticObjectId] = None  # None = root-level
    size: int = 0  # Total size of all files in this folder and its subfolders recursively
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: int  # Telegram user ID of the admin who created this folder

    class Settings:
        name = "folders"
        indexes = [
            # Fast O(1) children lookup AND sort — used on every directory browse
            # Enforces unique folder names within the same parent
            IndexModel(
                [("parent_id", ASCENDING), ("name", ASCENDING)],
                unique=True,
                name="unique_sibling_name",
            ),
        ]

    def __repr__(self) -> str:
        return f"<Folder id={self.id} name={self.name!r} parent={self.parent_id}>"
