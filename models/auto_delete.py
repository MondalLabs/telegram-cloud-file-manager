"""
models/auto_delete.py
─────────────────────────────────────────────────────────────────────────────
Beanie Document representing a scheduled message auto-delete job.
"""

from __future__ import annotations

from datetime import datetime
from beanie import Document
from pymongo import IndexModel, ASCENDING


class AutoDeleteJob(Document):
    chat_id: int
    message_id: int
    delete_at: datetime

    class Settings:
        name = "auto_delete_jobs"
        indexes = [
            # Compound index to ensure uniqueness per message and speed up query cleanups
            IndexModel([("chat_id", ASCENDING), ("message_id", ASCENDING)], unique=True),
            # Index on delete_at for fast retrieval of expired jobs
            IndexModel([("delete_at", ASCENDING)]),
        ]

    def __repr__(self) -> str:
        return f"<AutoDeleteJob id={self.id} chat={self.chat_id} msg={self.message_id} at={self.delete_at}>"
