"""
models/file.py
─────────────────────────────────────────────────────────────────────────────
Beanie Document representing a media file (video or document) stored in the
Telegram CDN (dump group).

All metadata fields are auto-extracted from Telegram's MTProto message object
via Safeguard #4's media = message.video or message.document pattern —
zero manual input required.

The file_id is the permanent Telegram CDN token used to stream the video
back to users without re-uploading or touching RAM (Safeguard #1).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from beanie import Document, PydanticObjectId
from pydantic import Field
from pymongo import IndexModel, ASCENDING


class File(Document):
    # ── Identity ──────────────────────────────────────────────────────────────
    name: str                              # Display name (defaults to original filename)
    file_id: str                           # Permanent Telegram CDN token
    file_type: str = "video"               # "video" | "document" — future-proof

    # ── Hierarchy ─────────────────────────────────────────────────────────────
    folder_id: Optional[PydanticObjectId] = None  # None = root level

    # ── Auto-extracted metadata (Safeguard #4: getattr-safe access) ───────────
    file_size: Optional[int] = None        # Bytes
    duration: Optional[int] = None         # Seconds (None for documents)
    width: Optional[int] = None            # Pixels (None for documents)
    height: Optional[int] = None           # Pixels (None for documents)
    mime_type: Optional[str] = None        # e.g. "video/mp4"

    # ── Audit ─────────────────────────────────────────────────────────────────
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    uploaded_by: int                       # Telegram user ID of uploader

    class Settings:
        name = "files"
        indexes = [
            # Fast O(1) folder content lookup and sort — used on every directory browse
            IndexModel([("folder_id", ASCENDING), ("name", ASCENDING)]),
        ]

    def __repr__(self) -> str:
        return f"<File id={self.id} name={self.name!r} folder={self.folder_id}>"

    @property
    def icon(self) -> str:
        """Return an emoji that represents the file type, based on mime_type."""
        mt = self.mime_type or ""
        if mt.startswith("video/"):              return "🎬"
        if mt.startswith("image/"):              return "🖼️"
        if mt == "application/pdf":              return "📄"
        if mt.startswith("audio/"):              return "🎵"
        if mt.startswith("text/"):               return "📝"
        if self.file_type == "video":            return "🎬"
        return "📎"  # generic document

    @property
    def display_meta(self) -> str:
        """Human-readable metadata string for upload confirmation messages."""
        parts = []
        if self.duration is not None:
            m, s = divmod(self.duration, 60)
            parts.append(f"{m}m{s:02d}s" if m else f"{s}s")
        if self.width and self.height:
            parts.append(f"{self.width}×{self.height}")
        if self.file_size:
            mb = self.file_size / (1024 * 1024)
            parts.append(f"{mb:.1f} MB")
        return " · ".join(parts) if parts else "media"
