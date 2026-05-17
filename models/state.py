"""
models/state.py
─────────────────────────────────────────────────────────────────────────────
Beanie Document for MongoDB-backed FSM state storage.

Why MongoDB instead of in-memory dicts?
  • Survives Render restarts / deployments — no lost conversation contexts.
  • Works correctly if Render ever runs multiple instances (stateless design).

Each user gets at most one document in this collection (upsert pattern).
The document is deleted once the FSM workflow completes (clear_state).
"""

from __future__ import annotations

from typing import Any, Optional

from beanie import Document
from pydantic import Field
from pymongo import IndexModel, ASCENDING


class FSMState(Document):
    telegram_id: int                       # Owner of this state context
    state: Optional[str] = None            # e.g. "create_folder:waiting_name"
    data: dict[str, Any] = Field(default_factory=dict)  # Arbitrary context bag

    class Settings:
        name = "states"
        indexes = [
            IndexModel([("telegram_id", ASCENDING)], unique=True),
        ]

    def __repr__(self) -> str:
        return f"<FSMState user={self.telegram_id} state={self.state!r}>"
