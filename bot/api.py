import logging
import asyncio
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Header, HTTPException, Depends
from pydantic import BaseModel, Field
from beanie import PydanticObjectId

from bot.config import settings
from bot.client import bot as tg_bot
from utils.auth import verify_telegram_init_data
from models.user import User, UserRole
from models.folder import Folder
from models.file import File
from models.settings import BotSettings

import services.user_service as user_service
import services.folder_service as folder_service
import services.file_service as file_service
import handlers.playback as playback

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# ── Pydantic Request schemas ──────────────────────────────────────────────────

class FolderCreateRequest(BaseModel):
    name: str = Field(..., max_length=128)
    parent_id: Optional[str] = None

class FolderRenameRequest(BaseModel):
    folder_id: str
    new_name: str = Field(..., max_length=128)

class FolderDeleteRequest(BaseModel):
    folder_id: str

class FileRenameRequest(BaseModel):
    file_id: str
    new_name: str = Field(..., max_length=128)

class FileDeleteRequest(BaseModel):
    file_id: str

class FilePlayRequest(BaseModel):
    file_id: str

class UserExceptionRequest(BaseModel):
    user_doc_id: str
    folder_id: str

class UserResetRequest(BaseModel):
    user_doc_id: str

class UserRevokeRequest(BaseModel):
    user_doc_id: str

class FolderMoveRequest(BaseModel):
    folder_id: str
    target_parent_id: Optional[str] = None

class FolderCopyRequest(BaseModel):
    folder_id: str
    target_parent_id: Optional[str] = None

class FileMoveRequest(BaseModel):
    file_id: str
    target_folder_id: Optional[str] = None

class FileCopyRequest(BaseModel):
    file_id: str
    target_folder_id: Optional[str] = None

class UserApproveRequest(BaseModel):
    user_doc_id: str

class PurgeBrokenRequest(BaseModel):
    file_ids: List[str]

class SettingsUpdateRequest(BaseModel):
    protect_content: Optional[bool] = None
    items_per_page: Optional[int] = None
    bot_name: Optional[str] = None
    auto_delete_hours: Optional[float] = None

# ── Dependency Injection Gating ────────────────────────────────────────────────

async def get_current_user(x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data")) -> User:
    """Verifies cryptographic signature of TMA initData and returns database user."""
    is_valid, user_data = verify_telegram_init_data(x_telegram_init_data, settings.bot_token)
    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid signature or session expired")

    telegram_id = user_data.get("id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Invalid user data structure")

    user = await user_service.get_or_create(
        telegram_id=telegram_id,
        full_name=user_data.get("first_name"),
        username=user_data.get("username")
    )

    if user.role == UserRole.GUEST:
        raise HTTPException(status_code=403, detail="Access denied. Your account is not approved.")

    return user

async def get_admin_user(user: User = Depends(get_current_user)) -> User:
    """Verifies that the caller has OWNER role."""
    if user.role != UserRole.OWNER:
        raise HTTPException(status_code=403, detail="Requires administrator access")
    return user

# ── API Endpoints ─────────────────────────────────────────────────────────────

@router.get("/user/me")
async def get_me(user: User = Depends(get_current_user)) -> dict:
    """Returns the authenticated user details."""
    return {
        "telegram_id": user.telegram_id,
        "display_name": user.display_name,
        "role": user.role,
        "allowed_folders": [str(fid) for fid in user.allowed_folders],
        "blocked_folders": [str(fid) for fid in user.blocked_folders]
    }

@router.get("/folders")
async def get_folders(folder_id: Optional[str] = None, user: User = Depends(get_current_user)) -> dict:
    """Retrieve child folders, files, and breadcrumbs for the directory."""
    parent_id_obj: Optional[PydanticObjectId] = None
    if folder_id and folder_id != "root":
        if not PydanticObjectId.is_valid(folder_id):
            raise HTTPException(status_code=400, detail="Invalid folder ID")
        parent_id_obj = PydanticObjectId(folder_id)

    # ── Exception Permissions Gate ──
    if parent_id_obj is not None:
        if not await user_service.has_folder_access(user, parent_id_obj):
            raise HTTPException(status_code=403, detail="Access Denied: Restricted folder")

    # Fetch folder details and breadcrumbs
    crumbs = []
    current_folder_name = "Root"
    if parent_id_obj:
        current_folder = await folder_service.get_folder(parent_id_obj)
        if not current_folder:
            raise HTTPException(status_code=404, detail="Folder not found")
        current_folder_name = current_folder.name
        
        raw_crumbs = await folder_service.get_breadcrumbs(parent_id_obj)
        crumbs = [{"id": str(c.id), "name": c.name} for c in raw_crumbs]

    # Fetch child items
    all_folders = await folder_service.get_children(parent_id_obj)
    all_files = await file_service.get_files_in_folder(parent_id_obj)

    # Filter folders by exceptions
    allowed_folders = []
    for f in all_folders:
        if await user_service.has_folder_access(user, f.id):
            allowed_folders.append({
                "id": str(f.id),
                "name": f.name,
                "size": getattr(f, "size", 0),
                "created_at": f.created_at.isoformat(),
                "created_by": f.created_by
            })

    # Files are accessible if user has file access to the parent folder
    allowed_files = []
    if await user_service.has_file_access(user, parent_id_obj):
        allowed_files = [{
            "id": str(f.id),
            "name": f.name,
            "file_type": f.file_type,
            "file_size": f.file_size,
            "duration": f.duration,
            "width": f.width,
            "height": f.height,
            "mime_type": f.mime_type,
            "uploaded_at": f.uploaded_at.isoformat(),
            "icon": f.icon
        } for f in all_files]

    return {
        "folder_id": folder_id or "root",
        "folder_name": current_folder_name,
        "breadcrumbs": crumbs,
        "folders": allowed_folders,
        "files": allowed_files
    }

@router.get("/folders/size")
async def api_get_folder_size(folder_id: str, user: User = Depends(get_current_user)) -> dict:
    """Get recursive size and contents count of a virtual folder."""
    if not PydanticObjectId.is_valid(folder_id):
        raise HTTPException(status_code=400, detail="Invalid folder ID")
    
    # Check permission
    folder_id_obj = PydanticObjectId(folder_id)
    if not await user_service.has_file_access(user, folder_id_obj):
        raise HTTPException(status_code=403, detail="Access Denied: Restricted folder")

    stats = await folder_service.get_folder_size(folder_id_obj)
    return stats

@router.post("/folders/create")
async def api_create_folder(req: FolderCreateRequest, user: User = Depends(get_admin_user)) -> dict:
    """Create a virtual folder (Admin only)."""
    parent_id_str = req.parent_id
    if parent_id_str == "root":
        parent_id_str = None

    parent_id_obj = None
    if parent_id_str:
        if not PydanticObjectId.is_valid(parent_id_str):
            raise HTTPException(status_code=400, detail="Invalid parent folder ID")
        parent_id_obj = PydanticObjectId(parent_id_str)

    try:
        folder = await folder_service.create_folder(
            name=req.name.strip(),
            parent_id=parent_id_obj,
            created_by=user.telegram_id
        )
        return {"status": "ok", "folder_id": str(folder.id), "name": folder.name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/folders/rename")
async def api_rename_folder(req: FolderRenameRequest, user: User = Depends(get_admin_user)) -> dict:
    """Rename a virtual folder (Admin only)."""
    if not PydanticObjectId.is_valid(req.folder_id):
        raise HTTPException(status_code=400, detail="Invalid folder ID")
    
    try:
        folder = await folder_service.rename_folder(PydanticObjectId(req.folder_id), req.new_name.strip())
        if not folder:
            raise HTTPException(status_code=404, detail="Folder not found")
        return {"status": "ok", "folder_id": str(folder.id), "name": folder.name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/folders/delete")
async def api_delete_folder(req: FolderDeleteRequest, user: User = Depends(get_admin_user)) -> dict:
    """Deletes a virtual folder subtree and its files (Admin only)."""
    if not PydanticObjectId.is_valid(req.folder_id):
        raise HTTPException(status_code=400, detail="Invalid folder ID")

    try:
        result = await folder_service.delete_folder_tree(PydanticObjectId(req.folder_id))
        return {
            "status": "ok",
            "folders_deleted": result["folders_deleted"],
            "files_deleted": result["files_deleted"]
        }
    except Exception as e:
        log.error("API folder delete error: %s", e)
        raise HTTPException(status_code=500, detail="Internal deletion error")

@router.post("/folders/move")
async def api_move_folder(req: FolderMoveRequest, user: User = Depends(get_admin_user)) -> dict:
    """Move a virtual folder (Admin only)."""
    if not PydanticObjectId.is_valid(req.folder_id):
        raise HTTPException(status_code=400, detail="Invalid folder ID")
    
    target_parent_id = None
    if req.target_parent_id and req.target_parent_id != "root":
        if not PydanticObjectId.is_valid(req.target_parent_id):
            raise HTTPException(status_code=400, detail="Invalid target parent folder ID")
        target_parent_id = PydanticObjectId(req.target_parent_id)

    try:
        folder = await folder_service.move_folder(PydanticObjectId(req.folder_id), target_parent_id)
        return {"status": "ok", "folder_id": str(folder.id), "name": folder.name, "parent_id": str(folder.parent_id) if folder.parent_id else None}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/folders/copy")
async def api_copy_folder(req: FolderCopyRequest, user: User = Depends(get_admin_user)) -> dict:
    """Copy a virtual folder recursively (Admin only)."""
    if not PydanticObjectId.is_valid(req.folder_id):
        raise HTTPException(status_code=400, detail="Invalid folder ID")
    
    target_parent_id = None
    if req.target_parent_id and req.target_parent_id != "root":
        if not PydanticObjectId.is_valid(req.target_parent_id):
            raise HTTPException(status_code=400, detail="Invalid target parent folder ID")
        target_parent_id = PydanticObjectId(req.target_parent_id)

    try:
        folder = await folder_service.copy_folder(PydanticObjectId(req.folder_id), target_parent_id, user.telegram_id)
        return {"status": "ok", "folder_id": str(folder.id), "name": folder.name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/files/move")
async def api_move_file(req: FileMoveRequest, user: User = Depends(get_admin_user)) -> dict:
    """Move a file reference (Admin only)."""
    if not PydanticObjectId.is_valid(req.file_id):
        raise HTTPException(status_code=400, detail="Invalid file ID")
    
    target_folder_id = None
    if req.target_folder_id and req.target_folder_id != "root":
        if not PydanticObjectId.is_valid(req.target_folder_id):
            raise HTTPException(status_code=400, detail="Invalid target folder ID")
        target_folder_id = PydanticObjectId(req.target_folder_id)

    f = await file_service.move_file(PydanticObjectId(req.file_id), target_folder_id)
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    return {"status": "ok", "file_id": str(f.id), "name": f.name}

@router.post("/files/copy")
async def api_copy_file(req: FileCopyRequest, user: User = Depends(get_admin_user)) -> dict:
    """Copy a file reference (Admin only)."""
    if not PydanticObjectId.is_valid(req.file_id):
        raise HTTPException(status_code=400, detail="Invalid file ID")
    
    target_folder_id = None
    if req.target_folder_id and req.target_folder_id != "root":
        if not PydanticObjectId.is_valid(req.target_folder_id):
            raise HTTPException(status_code=400, detail="Invalid target folder ID")
        target_folder_id = PydanticObjectId(req.target_folder_id)

    f = await file_service.copy_file(PydanticObjectId(req.file_id), target_folder_id, user.telegram_id)
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    return {"status": "ok", "file_id": str(f.id), "name": f.name}

@router.post("/files/rename")
async def api_rename_file(req: FileRenameRequest, user: User = Depends(get_admin_user)) -> dict:
    """Rename an indexed file (Admin only)."""
    if not PydanticObjectId.is_valid(req.file_id):
        raise HTTPException(status_code=400, detail="Invalid file ID")

    f = await file_service.rename_file(PydanticObjectId(req.file_id), req.new_name.strip())
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    return {"status": "ok", "file_id": str(f.id), "name": f.name}

@router.post("/files/delete")
async def api_delete_file(req: FileDeleteRequest, user: User = Depends(get_admin_user)) -> dict:
    """Delete an indexed file reference (Admin only)."""
    if not PydanticObjectId.is_valid(req.file_id):
        raise HTTPException(status_code=400, detail="Invalid file ID")

    success = await file_service.delete_file(PydanticObjectId(req.file_id))
    if not success:
        raise HTTPException(status_code=404, detail="File not found")
    return {"status": "ok"}

@router.post("/files/play")
async def api_play_file(req: FilePlayRequest, user: User = Depends(get_current_user)) -> dict:
    """Delivers the requested media to the user's private Telegram chat."""
    if not PydanticObjectId.is_valid(req.file_id):
        raise HTTPException(status_code=400, detail="Invalid file ID")

    f = await file_service.get_file(PydanticObjectId(req.file_id))
    if not f:
        raise HTTPException(status_code=404, detail="File not found")

    # Check permission exceptions
    if not await user_service.has_file_access(user, f.folder_id):
        raise HTTPException(status_code=403, detail="Access Denied: Restricted folder")

    # Fetch caption formatting and trigger MTProto client send
    caption = await playback._build_caption(f)
    chat_id = user.telegram_id

    try:
        if f.file_type == "video":
            sent = await tg_bot.send_video(
                chat_id=chat_id,
                video=f.file_id,
                caption=caption,
                supports_streaming=True,
                protect_content=settings.protect_content
            )
        elif f.file_type == "photo":
            sent = await tg_bot.send_photo(
                chat_id=chat_id,
                photo=f.file_id,
                caption=caption,
                protect_content=settings.protect_content
            )
        else:
            sent = await tg_bot.send_document(
                chat_id=chat_id,
                document=f.file_id,
                caption=caption,
                protect_content=settings.protect_content
            )

        # Trigger auto-delete scheduler if enabled
        if settings.auto_delete_hours > 0:
            delay = int(settings.auto_delete_hours * 3600)
            asyncio.create_task(playback._auto_delete_msg(tg_bot, chat_id, sent.id, delay))

        return {"status": "ok", "delivered_to": chat_id}

    except Exception as e:
        log.error("API playback delivery error: %s", e)
        raise HTTPException(status_code=500, detail=f"Playback delivery failed: {str(e)}")

# ── Admin Exceptions Management Endpoints ─────────────────────────────────────

@router.get("/admin/users")
async def get_admin_users(user: User = Depends(get_admin_user)) -> List[dict]:
    """Returns a list of all non-owner users and their exceptions (Admin only)."""
    users = await User.find(User.role != UserRole.OWNER).sort(+User.full_name).to_list()
    res = []
    for u in users:
        # Resolve folders names
        allowed_names = []
        for fid in u.allowed_folders:
            folder = await Folder.get(fid)
            if folder:
                allowed_names.append({"id": str(folder.id), "name": folder.name})

        blocked_names = []
        for fid in u.blocked_folders:
            folder = await Folder.get(fid)
            if folder:
                blocked_names.append({"id": str(folder.id), "name": folder.name})

        res.append({
            "user_doc_id": str(u.id),
            "telegram_id": u.telegram_id,
            "display_name": u.display_name,
            "username": u.username,
            "role": u.role,
            "approved_at": u.approved_at.isoformat() if u.approved_at else None,
            "allowed_folders": allowed_names,
            "blocked_folders": blocked_names
        })
    return res

@router.post("/admin/users/exceptions/allow")
async def api_allow_folder(req: UserExceptionRequest, user: User = Depends(get_admin_user)) -> dict:
    """Add an allowed folder exception (Admin only)."""
    if not PydanticObjectId.is_valid(req.folder_id):
        raise HTTPException(status_code=400, detail="Invalid folder ID")
    
    target = await user_service.find_user_by_id_doc(req.user_doc_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    await user_service.allow_folder_for_user(target, PydanticObjectId(req.folder_id))
    return {"status": "ok"}

@router.post("/admin/users/exceptions/block")
async def api_block_folder(req: UserExceptionRequest, user: User = Depends(get_admin_user)) -> dict:
    """Add a blocked folder exception (Admin only)."""
    if not PydanticObjectId.is_valid(req.folder_id):
        raise HTTPException(status_code=400, detail="Invalid folder ID")
    
    target = await user_service.find_user_by_id_doc(req.user_doc_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    await user_service.block_folder_for_user(target, PydanticObjectId(req.folder_id))
    return {"status": "ok"}

@router.post("/admin/users/exceptions/reset")
async def api_reset_folder(req: UserResetRequest, user: User = Depends(get_admin_user)) -> dict:
    """Reset folder exceptions for a user (Admin only)."""
    target = await user_service.find_user_by_id_doc(req.user_doc_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    await user_service.reset_folder_permissions_for_user(target)
    return {"status": "ok"}

@router.post("/admin/users/approve")
async def api_approve_user(req: UserApproveRequest, user: User = Depends(get_admin_user)) -> dict:
    """Approve guest user access (Admin only)."""
    target = await user_service.find_user_by_id_doc(req.user_doc_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    await user_service.approve_user(target.telegram_id, approved_by=user.telegram_id)
    return {"status": "ok"}

@router.post("/admin/users/revoke")
async def api_revoke_user(req: UserRevokeRequest, user: User = Depends(get_admin_user)) -> dict:
    """Revoke user access (Admin only)."""
    target = await user_service.find_user_by_id_doc(req.user_doc_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    await user_service.revoke_user(target.telegram_id)
    return {"status": "ok"}

@router.get("/admin/stats")
async def get_admin_stats(user: User = Depends(get_admin_user)) -> dict:
    """Returns storage metrics and user statistics (Admin only)."""
    total_folders = await Folder.count()
    total_files = await File.count()
    
    # Storage size aggregation
    pipeline = [
        {"$group": {"_id": None, "total_size": {"$sum": "$file_size"}}}
    ]
    size_res = await File.aggregate(pipeline).to_list(1)
    total_size = size_res[0]["total_size"] if size_res else 0

    # Type breakdown (group by file_type)
    type_pipeline = [
        {"$group": {"_id": "$file_type", "count": {"$sum": 1}, "size": {"$sum": "$file_size"}}}
    ]
    type_res = await File.aggregate(type_pipeline).to_list(10)
    file_types = {r["_id"]: {"count": r["count"], "size": r["size"]} for r in type_res}

    # User counts
    total_users = await User.count()
    approved_users = await User.find(User.role == UserRole.APPROVED).count()
    guest_users = await User.find(User.role == UserRole.GUEST).count()
    owner_users = await User.find(User.role == UserRole.OWNER).count()

    return {
        "folders_count": total_folders,
        "files_count": total_files,
        "total_size": total_size,
        "file_types": file_types,
        "users": {
            "total": total_users,
            "approved": approved_users,
            "guest": guest_users,
            "owner": owner_users
        }
    }

@router.post("/admin/health-check")
async def api_run_health_check(user: User = Depends(get_admin_user)) -> dict:
    """Performs integrity checks of storage files in dump group CDN (Admin only)."""
    dump_chat_id = await BotSettings.get_dump_chat_id(fallback=settings.dump_chat_id)
    if dump_chat_id is None:
        raise HTTPException(status_code=400, detail="Dump storage group is not configured")

    all_files = await File.find_all().to_list()
    total_files = len(all_files)
    if total_files == 0:
        return {"total": 0, "active": 0, "legacy": 0, "broken": []}

    legacy_count = 0
    verifiable = []
    for f in all_files:
        if f.dump_message_id is None:
            legacy_count += 1
        else:
            verifiable.append(f)

    broken_files = []
    verified_count = 0
    batch_size = 200

    for i in range(0, len(verifiable), batch_size):
        batch = verifiable[i : i + batch_size]
        msg_ids = [f.dump_message_id for f in batch]

        try:
            tg_msgs = await tg_bot.get_messages(chat_id=dump_chat_id, message_ids=msg_ids)
            if not isinstance(tg_msgs, list):
                tg_msgs = [tg_msgs]
        except Exception as e:
            log.error("API health check MTProto batch fetch error: %s", e)
            raise HTTPException(status_code=500, detail=f"Failed to query Telegram storage: {str(e)}")

        for idx, f in enumerate(batch):
            tg_msg = tg_msgs[idx] if idx < len(tg_msgs) else None
            is_deleted = tg_msg is None or getattr(tg_msg, "empty", False)
            if is_deleted:
                path_str = "Root"
                if f.folder_id:
                    try:
                        crumbs = await folder_service.get_breadcrumbs(f.folder_id)
                        path_str = " > ".join(c.name for c in crumbs)
                    except Exception:
                        path_str = "Unknown Folder"
                broken_files.append({
                    "id": str(f.id),
                    "name": f.name,
                    "folder_path": path_str
                })
            else:
                verified_count += 1

        await asyncio.sleep(1.0)

    return {
        "total": total_files,
        "active": verified_count,
        "legacy": legacy_count,
        "broken": broken_files
    }

@router.get("/admin/folders/all")
async def get_all_folders(user: User = Depends(get_admin_user)) -> List[dict]:
    """Returns a list of all folders in the database sorted by name (Admin only)."""
    all_folders = await Folder.find_all().sort(+Folder.name).to_list()
    return [{"id": str(f.id), "name": f.name} for f in all_folders]

@router.post("/admin/users/exceptions/remove")
async def api_remove_exception(req: UserExceptionRequest, user: User = Depends(get_admin_user)) -> dict:
    """Remove a folder exception (Allow or Block) for a user (Admin only)."""
    if not PydanticObjectId.is_valid(req.folder_id):
        raise HTTPException(status_code=400, detail="Invalid folder ID")
    
    target = await user_service.find_user_by_id_doc(req.user_doc_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    folder_id_obj = PydanticObjectId(req.folder_id)
    if folder_id_obj in target.allowed_folders:
        target.allowed_folders.remove(folder_id_obj)
    if folder_id_obj in target.blocked_folders:
        target.blocked_folders.remove(folder_id_obj)
        
    await target.save()
    return {"status": "ok"}

@router.post("/admin/purge-broken")
async def api_purge_broken(req: PurgeBrokenRequest, user: User = Depends(get_admin_user)) -> dict:
    """Deletes broken file references from the database (Admin only)."""
    count = 0
    for fid in req.file_ids:
        if PydanticObjectId.is_valid(fid):
            success = await file_service.delete_file(PydanticObjectId(fid))
            if success:
                count += 1
    return {"status": "ok", "purged_count": count}


def get_settings_response(db_settings: BotSettings) -> dict:
    return {
        "settings": {
            "protect_content": settings.protect_content,
            "items_per_page": settings.items_per_page,
            "bot_name": settings.bot_name,
            "auto_delete_hours": settings.auto_delete_hours
        },
        "defaults": {
            "protect_content": settings._raw_settings.protect_content,
            "items_per_page": settings._raw_settings.items_per_page,
            "bot_name": settings._raw_settings.bot_name,
            "auto_delete_hours": settings._raw_settings.auto_delete_hours
        },
        "overrides": {
            "protect_content": db_settings.protect_content is not None,
            "items_per_page": db_settings.items_per_page is not None,
            "bot_name": db_settings.bot_name is not None,
            "auto_delete_hours": db_settings.auto_delete_hours is not None
        }
    }

@router.get("/admin/settings")
async def api_get_admin_settings(user: User = Depends(get_admin_user)) -> dict:
    """Returns dynamic application settings configuration (Admin only)."""
    db_settings = await BotSettings.get_global()
    return get_settings_response(db_settings)

@router.post("/admin/settings")
async def api_update_admin_settings(req: SettingsUpdateRequest, user: User = Depends(get_admin_user)) -> dict:
    """Updates dynamic application settings configuration (Admin only)."""
    db_settings = await BotSettings.get_global()
    update_data = req.model_dump(exclude_unset=True)

    if "protect_content" in update_data:
        db_settings.protect_content = update_data["protect_content"]

    if "items_per_page" in update_data:
        v = update_data["items_per_page"]
        if v is not None and (v < 1 or v > 100):
            raise HTTPException(status_code=400, detail="Items per page must be between 1 and 100")
        db_settings.items_per_page = v

    if "bot_name" in update_data:
        v = update_data["bot_name"]
        if v is not None:
            v_stripped = v.strip()
            if len(v_stripped) > 64:
                raise HTTPException(status_code=400, detail="Bot name must be 64 characters or less")
            db_settings.bot_name = v_stripped if v_stripped else None
        else:
            db_settings.bot_name = None

    if "auto_delete_hours" in update_data:
        v = update_data["auto_delete_hours"]
        if v is not None and (v < 0 or v > 720):
            raise HTTPException(status_code=400, detail="Auto delete hours must be between 0 and 720")
        db_settings.auto_delete_hours = v

    await db_settings.save()

    # Update dynamic settings in-memory cache
    settings.update_cache(
        protect_content=db_settings.protect_content,
        items_per_page=db_settings.items_per_page,
        bot_name=db_settings.bot_name,
        auto_delete_hours=db_settings.auto_delete_hours
    )

    # Dynamic reload of Telegram commands if bot is connected
    if tg_bot.is_connected:
        try:
            from pyrogram.types import BotCommand
            display_name = settings.display_name
            _start_desc = f"📁 Open {display_name}" if display_name else "📁 Open the File Manager"
            await tg_bot.set_bot_commands([
                BotCommand("start",  _start_desc),
                BotCommand("done",   "✅ Finish current upload session"),
                BotCommand("cancel", "❌ Cancel current operation"),
            ])
            log.info("Telegram commands refreshed to display name: %s", display_name)
        except Exception as e:
            log.error("Failed to dynamically refresh bot commands: %s", e)

    return get_settings_response(db_settings)
