"""
services/file_service.py
─────────────────────────────────────────────────────────────────────────────
Business logic for file/video management and CDN routing.

Critical patterns enforced here:
  • Safeguard #1: route_to_cdn uses copy_message() — NEVER download_media().
    This is a server-side copy on Telegram's infrastructure; the bot process
    touches ZERO bytes of the file payload, preventing OOM on Render.

  • Safeguard #4: media detection uses (message.video or message.document)
    with getattr() for optional fields, handling both Telegram media types
    without NoneType errors.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from beanie import PydanticObjectId

from models.file import File
from models.settings import BotSettings
from bot.config import settings as cfg

if TYPE_CHECKING:
    from pyrogram import Client
    from pyrogram.types import Message


async def get_files_in_folder(folder_id: Optional[PydanticObjectId]) -> list[File]:
    """Return all files in a folder, ordered by name ascending."""
    return await File.find(
        File.folder_id == folder_id
    ).sort(+File.name).to_list()


async def count_files_in_folder(folder_id: Optional[PydanticObjectId]) -> int:
    """Return the total count of files in a folder."""
    return await File.find(File.folder_id == folder_id).count()


async def get_files_in_folder_paginated(
    folder_id: Optional[PydanticObjectId], skip: int, limit: int
) -> list[File]:
    """Return a paginated slice of files in a folder, ordered by name ascending."""
    return (
        await File.find(File.folder_id == folder_id)
        .sort(+File.name)
        .skip(skip)
        .limit(limit)
        .to_list()
    )


async def get_file(file_doc_id: PydanticObjectId) -> Optional[File]:
    """Fetch a single File document by its MongoDB _id."""
    return await File.get(file_doc_id)


async def create_file(
    *,
    name: str,
    file_id: str,
    file_type: str,
    folder_id: PydanticObjectId,
    uploaded_by: int,
    file_size: Optional[int] = None,
    duration: Optional[int] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    mime_type: Optional[str] = None,
    dump_message_id: Optional[int] = None,
) -> File:
    """Insert a new File document. All metadata already extracted by caller."""
    f = File(
        name=name,
        file_id=file_id,
        file_type=file_type,
        folder_id=folder_id,
        uploaded_by=uploaded_by,
        file_size=file_size,
        duration=duration,
        width=width,
        height=height,
        mime_type=mime_type,
        dump_message_id=dump_message_id,
    )
    await f.insert()
    return f


async def rename_file(file_doc_id: PydanticObjectId, new_name: str) -> Optional[File]:
    """Update the display name of a file. Returns updated doc or None."""
    f = await File.get(file_doc_id)
    if f is None:
        return None
    f.name = new_name
    await f.save()
    return f


async def delete_file(file_doc_id: PydanticObjectId) -> bool:
    """
    Remove a File document from MongoDB.
    The actual media remains in the Telegram CDN dump group (unreferenced).
    Returns True if deleted, False if not found.
    """
    f = await File.get(file_doc_id)
    if f is None:
        return False
    await f.delete()
    return True


async def route_to_cdn(
    client: "Client",
    message: "Message",
    folder_id: PydanticObjectId,
    uploaded_by: int,
) -> File:
    """
    Route an incoming video/document to the Telegram dump group CDN and
    index it in MongoDB.

    Safeguard #1 — Zero-copy:
      Uses client.copy_message() which performs a server-side copy.
      The bot process NEVER downloads the file into memory.

    Safeguard #4 — video vs document:
      media = message.video or message.document
      Optional fields accessed via getattr() with None fallback.

    Returns the created File document.
    Raises RuntimeError if the dump group is not configured.
    """
    # Resolve dump_chat_id: DB value takes precedence over env var
    dump_chat_id = await BotSettings.get_dump_chat_id(fallback=cfg.dump_chat_id)
    if dump_chat_id is None:
        raise RuntimeError(
            "Dump group not configured. "
            "Please send /setup inside your private dump group first."
        )

    # ── Safeguard #4: detect media type ──────────────────────────────────────
    if message.photo:
        # Photos are the largest-size Photo object (not a list in Pyrofork)
        media = message.photo
        file_type = "photo"
    elif message.video:
        media = message.video
        file_type = "video"
    elif message.document:
        media = message.document
        file_type = "document"
    else:
        raise ValueError("Message contains no supported media (video, document, or photo).")

    # ── Safeguard #1: server-side copy — zero RAM ─────────────────────────────
    copied_msg = await client.copy_message(
        chat_id=dump_chat_id,
        from_chat_id=message.chat.id,
        message_id=message.id,
    )

    # Extract the permanent file_id from the dump group copy
    copied_media = copied_msg.video or copied_msg.document or copied_msg.photo
    if copied_media is None:
        raise RuntimeError("CDN copy failed — no media in forwarded message.")

    cdn_file_id = copied_media.file_id

    # ── Safeguard #4: safe metadata extraction via getattr ────────────────────
    # Photos: no file_name, mime_type defaults to image/jpeg
    raw_name: str = (
        getattr(media, "file_name", None)
        or (f"photo_{message.id}.jpg" if file_type == "photo" else f"file_{message.id}")
    )

    # 🛡️ Security: Enforce length limit (max 128) to prevent MessageTooLong DoS
    if len(raw_name) > 128:
        parts = raw_name.rsplit(".", 1)
        if len(parts) == 2 and len(parts[1]) < 10:
            ext = parts[1]
            raw_name = parts[0][:128 - len(ext) - 1] + "." + ext
        else:
            raw_name = raw_name[:128]

    file_size: Optional[int] = getattr(media, "file_size", None)
    duration_raw = getattr(media, "duration", None)
    duration: Optional[int] = int(duration_raw) if duration_raw is not None else None
    width: Optional[int] = getattr(media, "width", None)
    height: Optional[int] = getattr(media, "height", None)
    mime_type: Optional[str] = getattr(media, "mime_type", None) or (
        "image/jpeg" if file_type == "photo" else None
    )

    return await create_file(
        name=raw_name,
        file_id=cdn_file_id,
        file_type=file_type,
        folder_id=folder_id,
        uploaded_by=uploaded_by,
        file_size=file_size,
        duration=duration,
        width=width,
        height=height,
        mime_type=mime_type,
        dump_message_id=copied_msg.id,
    )
