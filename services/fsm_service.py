"""
services/fsm_service.py
─────────────────────────────────────────────────────────────────────────────
MongoDB-backed Finite State Machine (FSM) helper functions.

Why MongoDB instead of in-memory?
  • Survives Render restarts — ongoing admin workflows aren't lost.
  • Naturally scales if Render ever adds more instances.

State naming convention:  "{workflow}:{step}"
  e.g.  "create_folder:waiting_name"
        "upload:waiting_files"
        "rename_file:waiting_name"
        "approve_user:waiting_id"
"""

from __future__ import annotations

from typing import Any, Optional

from models.state import FSMState


async def get_state(telegram_id: int) -> Optional[str]:
    """Return the current FSM state string for a user, or None if idle."""
    doc = await FSMState.find_one(FSMState.telegram_id == telegram_id)
    return doc.state if doc else None


async def get_data(telegram_id: int) -> dict[str, Any]:
    """Return the FSM context data dict for a user (empty dict if idle)."""
    doc = await FSMState.find_one(FSMState.telegram_id == telegram_id)
    return doc.data if doc else {}


async def get_state_and_data(telegram_id: int) -> tuple[Optional[str], dict[str, Any]]:
    """Fetch both state and data in a single DB round-trip."""
    doc = await FSMState.find_one(FSMState.telegram_id == telegram_id)
    if doc is None:
        return None, {}
    return doc.state, doc.data


async def set_state(
    telegram_id: int,
    state: str,
    data: Optional[dict[str, Any]] = None,
) -> FSMState:
    """
    Create or replace the FSM state for a user.
    data defaults to an empty dict if not provided.
    """
    doc = await FSMState.find_one(FSMState.telegram_id == telegram_id)
    if doc is None:
        doc = FSMState(telegram_id=telegram_id, state=state, data=data or {})
        await doc.insert()
    else:
        doc.state = state
        doc.data = data or {}
        await doc.save()
    return doc


async def update_data(telegram_id: int, **kwargs: Any) -> None:
    """
    Merge kwargs into the user's FSM data dict without overwriting other keys.
    Example: await fsm_service.update_data(user_id, folder_id="abc123")
    """
    doc = await FSMState.find_one(FSMState.telegram_id == telegram_id)
    if doc is None:
        # Create an idle document with just the data
        doc = FSMState(telegram_id=telegram_id, state=None, data=kwargs)
        await doc.insert()
    else:
        doc.data.update(kwargs)
        await doc.save()


async def clear_state(telegram_id: int) -> None:
    """
    Delete the FSM state document for a user, returning them to idle.
    Safe to call even if no state exists (no-op).
    """
    doc = await FSMState.find_one(FSMState.telegram_id == telegram_id)
    if doc is not None:
        await doc.delete()
