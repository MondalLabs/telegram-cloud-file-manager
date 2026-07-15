"""
services/auto_delete_service.py
─────────────────────────────────────────────────────────────────────────────
All logic for scheduling, memory-hydration, and message deletions.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING

from models.auto_delete import AutoDeleteJob

if TYPE_CHECKING:
    from pyrogram import Client

log = logging.getLogger(__name__)


async def schedule_auto_delete(client: Client, chat_id: int, message_id: int, hours: float) -> None:
    """
    Saves the auto-deletion metadata into MongoDB and schedules
    an exact-second in-memory deletion task.
    """
    delete_at = datetime.now(timezone.utc) + timedelta(hours=hours)
    
    # Persist job record in DB
    job = AutoDeleteJob(chat_id=chat_id, message_id=message_id, delete_at=delete_at)
    await job.insert()
    log.info("Scheduled auto-delete in DB for message %d in chat %d at %s", message_id, chat_id, delete_at)

    # Spawn in-memory task for exact-second deletion
    delay = int(hours * 3600)
    asyncio.create_task(_auto_delete_msg(client, chat_id, message_id, delay))


async def _auto_delete_msg(client: Client, chat_id: int, msg_id: int, delay: float) -> None:
    """
    Fire-and-forget task that sleeps for a delay, deletes the message,
    and removes the backup job from MongoDB.
    """
    if delay > 0:
        await asyncio.sleep(delay)
    
    # 1. Attempt Telegram deletion
    try:
        await client.delete_messages(chat_id, msg_id)
        log.info("Auto-deleted message %d in chat %d via in-memory task", msg_id, chat_id)
    except Exception as e:
        # Ignore already deleted or inaccessible messages
        log.debug("Failed Telegram message deletion for message %d in chat %d: %s", msg_id, chat_id, e)

    # 2. Clean up database record
    try:
        job = await AutoDeleteJob.find_one({"chat_id": chat_id, "message_id": msg_id})
        if job:
            await job.delete()
    except Exception as e:
        log.error("Failed to clean up AutoDeleteJob from DB for message %d: %s", msg_id, e)


async def hydrate_auto_deletions(client: Client) -> None:
    """
    Queries MongoDB for all pending auto-delete jobs:
      - If deletion time has already passed: deletes immediately and removes job.
      - If deletion time is in the future: schedules the remaining time in memory.
    """
    log.info("Hydrating auto-deletion tasks from MongoDB...")
    now = datetime.now(timezone.utc)
    
    try:
        pending_jobs = await AutoDeleteJob.find_all().to_list()
    except Exception as e:
        log.error("Failed to query pending auto-delete jobs on startup: %s", e)
        return

    log.info("Found %d pending auto-delete jobs in database.", len(pending_jobs))
    for job in pending_jobs:
        # Ensure delete_at is timezone-aware in UTC to prevent TypeError on subtraction
        delete_at = job.delete_at
        if delete_at.tzinfo is None:
            delete_at = delete_at.replace(tzinfo=timezone.utc)

        remaining = (delete_at - now).total_seconds()
        if remaining <= 0:
            log.info("Processing expired auto-deletion for message %d in chat %d", job.message_id, job.chat_id)
            try:
                await client.delete_messages(chat_id=job.chat_id, message_ids=job.message_id)
            except Exception as e:
                log.debug("Telegram deletion failed for expired message %d: %s", job.message_id, e)
            try:
                await job.delete()
            except Exception as e:
                log.error("Failed to delete expired AutoDeleteJob document: %s", e)
        else:
            log.info(
                "Rescheduling future auto-deletion for message %d in chat %d in %g seconds",
                job.message_id, job.chat_id, remaining
            )
            asyncio.create_task(_auto_delete_msg(client, job.chat_id, job.message_id, remaining))
