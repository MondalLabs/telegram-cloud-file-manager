"""
services/user_service.py
─────────────────────────────────────────────────────────────────────────────
RBAC whitelist management.

get_or_create() is the primary entry point — called on every incoming update
by the access_control middleware. It guarantees the user exists in the DB
before any role check is performed.

The OWNER role is bootstrapped automatically: if the incoming telegram_id
matches settings.owner_id and the DB has them as GUEST, they are upgraded
to OWNER on first contact.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from models.user import User, UserRole
from bot.config import settings as cfg


async def get_or_create(
    telegram_id: int,
    full_name: Optional[str] = None,
    username: Optional[str] = None,
) -> User:
    """
    Fetch an existing user or create a new GUEST record.
    Auto-promotes the bot owner to OWNER role on first contact.
    """
    user = await User.find_one(User.telegram_id == telegram_id)

    if user is None:
        role = UserRole.OWNER if telegram_id == cfg.owner_id else UserRole.GUEST
        user = User(
            telegram_id=telegram_id,
            full_name=full_name,
            username=username,
            role=role,
        )
        await user.insert()
    else:
        # Keep profile fields fresh (name/username can change in Telegram)
        updated = False
        if full_name and user.full_name != full_name:
            user.full_name = full_name
            updated = True
        if username and user.username != username:
            user.username = username
            updated = True
        # Safety net: ensure the owner is always OWNER even if DB was tampered
        if telegram_id == cfg.owner_id and user.role != UserRole.OWNER:
            user.role = UserRole.OWNER
            updated = True
        if updated:
            await user.save()

    return user


async def get_role(telegram_id: int) -> UserRole:
    """Return the role for a telegram_id, defaulting to GUEST if unknown."""
    user = await User.find_one(User.telegram_id == telegram_id)
    return user.role if user else UserRole.GUEST


async def approve_user(telegram_id: int, approved_by: int) -> Optional[User]:
    """Set a user's role to APPROVED. Returns None if user not found."""
    user = await User.find_one(User.telegram_id == telegram_id)
    if user is None:
        return None
    if user.role == UserRole.OWNER:
        raise ValueError("Cannot change the role of the bot owner.")
    user.role = UserRole.APPROVED
    user.approved_at = datetime.utcnow()
    user.approved_by = approved_by
    user.revoked_at = None
    await user.save()
    return user


async def revoke_user(telegram_id: int) -> Optional[User]:
    """Downgrade a user back to GUEST. Returns None if user not found."""
    user = await User.find_one(User.telegram_id == telegram_id)
    if user is None:
        return None
    if user.role == UserRole.OWNER:
        raise ValueError("Cannot revoke the bot owner's access.")
    user.role = UserRole.GUEST
    user.revoked_at = datetime.utcnow()
    await user.save()
    return user


async def list_approved() -> list[User]:
    """Return all currently approved (non-owner) users, sorted by name."""
    return await User.find(User.role == UserRole.APPROVED).sort(+User.full_name).to_list()


async def count_approved() -> int:
    """Return the total count of approved users."""
    return await User.find(User.role == UserRole.APPROVED).count()


async def get_approved_paginated(skip: int, limit: int) -> list[User]:
    """Return a paginated slice of approved users."""
    return (
        await User.find(User.role == UserRole.APPROVED)
        .sort(+User.full_name)
        .skip(skip)
        .limit(limit)
        .to_list()
    )


async def find_user_by_id(telegram_id: int) -> Optional[User]:
    """Fetch a user document by Telegram ID. Returns None if not found."""
    return await User.find_one(User.telegram_id == telegram_id)


async def find_user_by_id_doc(user_doc_id: str) -> Optional[User]:
    """Fetch a user document by its MongoDB _id string. Returns None if not found."""
    from beanie import PydanticObjectId
    try:
        return await User.get(PydanticObjectId(user_doc_id))
    except Exception:
        return None


async def has_file_access(user: User, folder_id: Optional[PydanticObjectId]) -> bool:
    """
    Evaluate file access to a specific folder:
    1. If user is OWNER: access is always granted.
    2. If folder_id is None (Root): viewable if allowed_folders is empty, otherwise blocked by default.
    3. Resolves using "closest rule wins" walking up the ancestor chain from the folder to root.
       The first matching rule (either in user.blocked_folders or user.allowed_folders) determines the result.
    4. If no rules match:
       - If user.allowed_folders is empty: allowed.
       - Otherwise: blocked (whitelist model).
    """
    if user.role == UserRole.OWNER:
        return True

    # Build ancestor path (including folder_id itself)
    import services.folder_service as folder_service
    path_ids = []
    
    if folder_id is not None:
        curr_id = folder_id
        while curr_id is not None:
            path_ids.append(curr_id)
            folder = await folder_service.get_folder(curr_id)
            if folder is None:
                break
            curr_id = folder.parent_id

    blocked_set = set(user.blocked_folders)
    allowed_set = set(user.allowed_folders)

    # Walk up the chain: closest rule wins
    for pid in path_ids:
        if pid in blocked_set:
            return False
        if pid in allowed_set:
            return True

    # If no rule was found in the hierarchy
    if not allowed_set:
        return True
    return False


async def has_folder_access(user: User, folder_id: Optional[PydanticObjectId]) -> bool:
    """
    Evaluate if a folder is navigable by the user:
    1. If folder_id is None (Root): always navigable.
    2. If the user has file access to this folder: navigable.
    3. If this folder is an ancestor of any folder in user.allowed_folders: navigable.
    """
    if user.role == UserRole.OWNER:
        return True

    if folder_id is None:
        return True

    # Direct access check
    if await has_file_access(user, folder_id):
        return True

    # Check if folder_id is an ancestor of any allowed folders
    import services.folder_service as folder_service
    for allowed_id in user.allowed_folders:
        curr_id = allowed_id
        while curr_id is not None:
            # Walk up to find folder_id
            if curr_id == folder_id:
                return True
            folder = await folder_service.get_folder(curr_id)
            if folder is None:
                break
            curr_id = folder.parent_id

    return False


async def allow_folder_for_user(user: User, folder_id: PydanticObjectId) -> None:
    """Explicitly allow a folder for a user. Clears it from blocked if present."""
    if folder_id in user.blocked_folders:
        user.blocked_folders.remove(folder_id)
    if folder_id not in user.allowed_folders:
        user.allowed_folders.append(folder_id)
    await user.save()


async def block_folder_for_user(user: User, folder_id: PydanticObjectId) -> None:
    """Explicitly block a folder for a user. Clears it from allowed if present."""
    if folder_id in user.allowed_folders:
        user.allowed_folders.remove(folder_id)
    if folder_id not in user.blocked_folders:
        user.blocked_folders.append(folder_id)
    await user.save()


async def reset_folder_permissions_for_user(user: User) -> None:
    """Clear all folder allow and block overrides for a user."""
    user.allowed_folders = []
    user.blocked_folders = []
    await user.save()
