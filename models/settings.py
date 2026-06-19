"""
models/settings.py
─────────────────────────────────────────────────────────────────────────────
Beanie Document for runtime bot configuration that can be changed live
without redeploying (e.g., the dump_chat_id set via /setup).

Uses a singleton pattern: always fetch the document with key="global".
"""

from __future__ import annotations

from typing import Optional

from beanie import Document
from pymongo import IndexModel, ASCENDING


class BotSettings(Document):
    key: str = "global"                    # Always "global" — singleton row
    dump_chat_id: Optional[int] = None     # Set via /setup, overrides env var
    protect_content: Optional[bool] = None  # Live override for protect_content
    items_per_page: Optional[int] = None   # Live override for items_per_page
    bot_name: Optional[str] = None         # Live override for bot_name
    auto_delete_hours: Optional[float] = None # Live override for auto_delete_hours

    class Settings:
        name = "bot_settings"
        indexes = [
            IndexModel([("key", ASCENDING)], unique=True),
        ]

    @classmethod
    async def get_global(cls) -> "BotSettings":
        """Fetch or create the singleton settings document."""
        doc = await cls.find_one(cls.key == "global")
        if doc is None:
            doc = cls()
            await doc.insert()
        return doc

    @classmethod
    async def get_dump_chat_id(cls, fallback: Optional[int] = None) -> Optional[int]:
        """Return the live dump_chat_id, falling back to env var value."""
        doc = await cls.get_global()
        return doc.dump_chat_id if doc.dump_chat_id is not None else fallback
