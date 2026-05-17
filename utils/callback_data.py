"""
utils/callback_data.py
─────────────────────────────────────────────────────────────────────────────
Structured callback data encoder / decoder.

Telegram enforces a hard 64-byte limit on callback_data strings.
(Safeguard #3 — one ObjectId max per callback.)

Encoding scheme: "{action}:{arg1}:{arg2}:..."
  • Fields separated by a single colon ":"
  • Action is always a short alpha prefix (2–4 chars)
  • At most ONE MongoDB ObjectId (24 chars) per callback string

Byte budget check:
  longest realistic callback: "nav:{24-char-oid}:{2-digit-page}"
  = 4 + 24 + 1 + 2 = 31 bytes — well within the 64-byte limit.

Public API:
  encode(action, *args) → str
  decode(data)          → tuple[str, ...]
  action_of(data)       → str   (first field only)
"""

from __future__ import annotations

SEPARATOR = ":"


def encode(action: str, *args: str | int) -> str:
    """
    Build a callback_data string.

    Example:
        encode("nav", "6a08ce62ae36ee491a35cd99", 2)
        → "nav:6a08ce62ae36ee491a35cd99:2"
    """
    parts = [action] + [str(a) for a in args]
    result = SEPARATOR.join(parts)
    assert len(result.encode()) <= 64, (
        f"Callback data exceeds 64 bytes: {result!r} ({len(result.encode())} bytes)"
    )
    return result


def decode(data: str) -> tuple[str, ...]:
    """
    Parse a callback_data string into a tuple of string parts.

    Example:
        decode("nav:6a08ce62ae36ee491a35cd99:2")
        → ("nav", "6a08ce62ae36ee491a35cd99", "2")
    """
    return tuple(data.split(SEPARATOR))


def action_of(data: str) -> str:
    """Return just the action prefix of a callback_data string."""
    return data.split(SEPARATOR, 1)[0]


# ── Registered action prefixes (single source of truth) ──────────────────────
#
# Keep this list updated as new handlers are added.
# Format: ACTION_* = "prefix"

ACTION_NAV       = "nav"      # nav:{folder_id}:{page}
ACTION_PLAY      = "play"     # play:{file_doc_id}
ACTION_CF        = "cf"       # cf:{parent_id}             create folder
ACTION_RF        = "rf"       # rf:{folder_id}             rename folder
ACTION_DF        = "df"       # df:{folder_id}             delete folder (show confirm)
ACTION_REN_FILE  = "renf"     # renf:{file_doc_id}         rename file
ACTION_DEL_FILE  = "delf"     # delf:{file_doc_id}         delete file (show confirm)
ACTION_UPL       = "upl"      # upl:{folder_id}            start upload FSM
ACTION_CONFIRM   = "yes"      # yes:{action}:{target_id}   confirmed destructive action
ACTION_CANCEL    = "cancel"   # cancel                     abort current FSM
ACTION_BACK      = "back"     # back:{parent_id}           navigate up
ACTION_FOLDER_INFO = "fi"     # fi:{folder_id}             folder action menu
ACTION_FILE_INFO   = "fli"    # fli:{file_doc_id}          file action menu

# User management
ACTION_USR_APPROVE = "ua"     # ua                         start approve flow
ACTION_USR_REVOKE  = "ur"     # ur:{user_doc_id}           revoke specific user
ACTION_USR_LIST    = "ul"     # ul:{page}                  list approved users
