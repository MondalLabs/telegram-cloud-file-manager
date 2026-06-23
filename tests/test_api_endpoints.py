import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from beanie import PydanticObjectId

from bot.api import router, get_current_user, get_admin_user
from models.user import User, UserRole
from models.folder import Folder
from models.file import File

# Setup Test FastAPI App
app = FastAPI()
app.include_router(router)

# Define mock users
mock_owner = MagicMock(spec=User)
mock_owner.role = UserRole.OWNER
mock_owner.telegram_id = 999

mock_approved = MagicMock(spec=User)
mock_approved.role = UserRole.APPROVED
mock_approved.telegram_id = 123

# Default override behaves as mock_approved
active_user = mock_approved

async def override_get_current_user():
    return active_user

async def override_get_admin_user():
    if active_user.role != UserRole.OWNER:
        raise HTTPException(status_code=403, detail="Requires administrator access")
    return active_user

app.dependency_overrides[get_current_user] = override_get_current_user
app.dependency_overrides[get_admin_user] = override_get_admin_user

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_active_user():
    global active_user
    active_user = mock_approved

# ── 1. GET /api/user/me ────────────────────────────────────────────────────────

def test_api_get_user_me():
    global active_user
    active_user = mock_approved
    
    mock_approved.telegram_id = 123
    mock_approved.full_name = "Approved User"
    mock_approved.username = "appuser"
    mock_approved.role = UserRole.APPROVED
    mock_approved.allowed_folders = []
    mock_approved.blocked_folders = []
    
    response = client.get("/api/user/me")
    assert response.status_code == 200
    data = response.json()
    assert data["telegram_id"] == 123
    assert data["role"] == "approved"

# ── 2. GET /api/folders ─────────────────────────────────────────────────────────

@patch("services.user_service.has_folder_access")
@patch("services.user_service.has_file_access")
@patch("services.folder_service.get_children")
@patch("services.file_service.get_files_in_folder")
def test_api_get_folders_root(mock_get_files, mock_get_children, mock_has_file, mock_has_folder):
    mock_has_folder.return_value = True
    mock_has_file.return_value = True
    
    # Mock folder child
    fld = MagicMock()
    fld.id = PydanticObjectId()
    fld.name = "Movies"
    fld.created_at.isoformat.return_value = "2026-06-19T00:00:00"
    fld.created_by = 999
    mock_get_children.return_value = [fld]
    
    # Mock file child
    fl = MagicMock()
    fl.id = PydanticObjectId()
    fl.name = "video.mp4"
    fl.file_type = "video"
    fl.file_size = 1024
    fl.duration = 100
    fl.width = 1920
    fl.height = 1080
    fl.mime_type = "video/mp4"
    fl.uploaded_at.isoformat.return_value = "2026-06-19T00:00:00"
    fl.icon = "🎥"
    mock_get_files.return_value = [fl]
    
    response = client.get("/api/folders")
    assert response.status_code == 200
    data = response.json()
    assert data["folder_name"] == "Root"
    assert len(data["folders"]) == 1
    assert data["folders"][0]["name"] == "Movies"
    assert len(data["files"]) == 1
    assert data["files"][0]["name"] == "video.mp4"

@patch("services.user_service.has_folder_access")
@patch("services.folder_service.get_folder")
def test_api_get_folders_permission_denied(mock_get_folder, mock_has_folder):
    mock_has_folder.return_value = False
    fid = PydanticObjectId()
    
    response = client.get(f"/api/folders?folder_id={fid}")
    assert response.status_code == 403
    assert "Access Denied" in response.json()["detail"]

def test_api_get_folders_invalid_id():
    response = client.get("/api/folders?folder_id=invalid")
    assert response.status_code == 400

# ── 3. GET /api/folders/size ───────────────────────────────────────────────────

@patch("services.user_service.has_file_access")
@patch("services.folder_service.get_folder_size")
def test_api_get_folder_size(mock_size, mock_has_file):
    mock_has_file.return_value = True
    mock_size.return_value = {"size": 500, "files_count": 2, "folders_count": 1}
    
    fid = PydanticObjectId()
    response = client.get(f"/api/folders/size?folder_id={fid}")
    assert response.status_code == 200
    assert response.json()["size"] == 500

# ── 4. POST /api/folders/create ────────────────────────────────────────────────

@patch("services.folder_service.create_folder")
def test_api_create_folder(mock_create):
    global active_user
    active_user = mock_owner
    
    folder = MagicMock(spec=Folder)
    folder.id = PydanticObjectId()
    folder.name = "New Folder"
    mock_create.return_value = folder
    
    response = client.post("/api/folders/create", json={"name": "New Folder", "parent_id": None})
    assert response.status_code == 200
    assert response.json()["name"] == "New Folder"

# ── 5. POST /api/folders/rename ────────────────────────────────────────────────

@patch("services.folder_service.rename_folder")
def test_api_rename_folder(mock_rename):
    global active_user
    active_user = mock_owner
    
    folder = MagicMock(spec=Folder)
    folder.id = PydanticObjectId()
    folder.name = "Renamed Folder"
    mock_rename.return_value = folder
    
    fid = PydanticObjectId()
    response = client.post("/api/folders/rename", json={"folder_id": str(fid), "new_name": "Renamed Folder"})
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed Folder"

# ── 6. POST /api/folders/delete ────────────────────────────────────────────────

@patch("services.folder_service.delete_folder_tree")
def test_api_delete_folder(mock_delete):
    global active_user
    active_user = mock_owner
    mock_delete.return_value = {"folders_deleted": 1, "files_deleted": 2}
    
    fid = PydanticObjectId()
    response = client.post("/api/folders/delete", json={"folder_id": str(fid)})
    assert response.status_code == 200
    assert response.json()["folders_deleted"] == 1

# ── 7. POST /api/folders/move ──────────────────────────────────────────────────

@patch("services.folder_service.move_folder")
def test_api_move_folder(mock_move):
    global active_user
    active_user = mock_owner
    
    folder = MagicMock(spec=Folder)
    folder.id = PydanticObjectId()
    folder.name = "Folder"
    folder.parent_id = PydanticObjectId()
    mock_move.return_value = folder
    
    fid = PydanticObjectId()
    pid = PydanticObjectId()
    response = client.post("/api/folders/move", json={"folder_id": str(fid), "target_parent_id": str(pid)})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

# ── 8. POST /api/folders/copy ──────────────────────────────────────────────────

@patch("services.folder_service.copy_folder")
def test_api_copy_folder(mock_copy):
    global active_user
    active_user = mock_owner
    
    folder = MagicMock(spec=Folder)
    folder.id = PydanticObjectId()
    folder.name = "Folder Copied"
    mock_copy.return_value = folder
    
    fid = PydanticObjectId()
    pid = PydanticObjectId()
    response = client.post("/api/folders/copy", json={"folder_id": str(fid), "target_parent_id": str(pid)})
    assert response.status_code == 200
    assert response.json()["name"] == "Folder Copied"

# ── 9. POST /api/files/rename ─────────────────────────────────────────────────

@patch("services.file_service.rename_file")
def test_api_rename_file(mock_rename):
    global active_user
    active_user = mock_owner
    
    fl = MagicMock(spec=File)
    fl.id = PydanticObjectId()
    fl.name = "renamed.txt"
    mock_rename.return_value = fl
    
    fid = PydanticObjectId()
    response = client.post("/api/files/rename", json={"file_id": str(fid), "new_name": "renamed.txt"})
    assert response.status_code == 200
    assert response.json()["name"] == "renamed.txt"

# ── 10. POST /api/files/delete ────────────────────────────────────────────────

@patch("services.file_service.delete_file")
def test_api_delete_file(mock_delete):
    global active_user
    active_user = mock_owner
    mock_delete.return_value = True
    
    fid = PydanticObjectId()
    response = client.post("/api/files/delete", json={"file_id": str(fid)})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

# ── 11. POST /api/files/play ──────────────────────────────────────────────────

@patch("bot.api.schedule_auto_delete", new_callable=AsyncMock)
@patch("services.user_service.has_file_access")
@patch("services.file_service.get_file")
@patch("handlers.playback._build_caption")
@patch("bot.api.tg_bot.send_video", new_callable=AsyncMock)
def test_api_play_file(mock_send_video, mock_caption, mock_get_file, mock_has_file, mock_schedule_delete):
    mock_has_file.return_value = True
    
    fl = MagicMock()
    fl.id = PydanticObjectId()
    fl.folder_id = PydanticObjectId()
    fl.file_type = "video"
    fl.file_id = "tg_video_id"
    mock_get_file.return_value = fl
    
    mock_caption.return_value = "Caption"
    mock_send_video.return_value = MagicMock(id=12345)
    
    fid = PydanticObjectId()
    response = client.post("/api/files/play", json={"file_id": str(fid)})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    mock_schedule_delete.assert_called_once()

# ── 12. POST /api/files/move ──────────────────────────────────────────────────

@patch("services.file_service.move_file")
def test_api_move_file(mock_move):
    global active_user
    active_user = mock_owner
    
    fl = MagicMock(spec=File)
    fl.id = PydanticObjectId()
    fl.name = "File"
    mock_move.return_value = fl
    
    fid = PydanticObjectId()
    folder_id = PydanticObjectId()
    response = client.post("/api/files/move", json={"file_id": str(fid), "target_folder_id": str(folder_id)})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

# ── 13. POST /api/files/copy ──────────────────────────────────────────────────

@patch("services.file_service.copy_file")
def test_api_copy_file(mock_copy):
    global active_user
    active_user = mock_owner
    
    fl = MagicMock(spec=File)
    fl.id = PydanticObjectId()
    fl.name = "File Copied"
    mock_copy.return_value = fl
    
    fid = PydanticObjectId()
    folder_id = PydanticObjectId()
    response = client.post("/api/files/copy", json={"file_id": str(fid), "target_folder_id": str(folder_id)})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

# ── 14. GET /api/admin/users ───────────────────────────────────────────────────

@patch("bot.api.Folder")
@patch("bot.api.User")
@patch("services.folder_service.get_breadcrumbs")
def test_api_get_users(mock_breadcrumbs, mock_user_class, mock_folder_class):
    global active_user
    active_user = mock_owner
    
    user = MagicMock()
    user.id = PydanticObjectId()
    user.telegram_id = 123
    user.full_name = "User"
    user.username = "user"
    user.role = UserRole.APPROVED
    user.allowed_folders = [PydanticObjectId()]
    user.blocked_folders = []
    user.approved_at = None
    
    mock_user_class.find.return_value.sort.return_value.to_list = AsyncMock(return_value=[user])
    
    mock_folder = MagicMock()
    mock_folder.id = PydanticObjectId()
    mock_folder.name = "Allowed Folder"
    mock_folder_class.get = AsyncMock(return_value=mock_folder)
    
    mock_breadcrumbs.return_value = []
    
    response = client.get("/api/admin/users")
    assert response.status_code == 200
    assert len(response.json()) == 1

# ── 15. POST /api/admin/users/approve ──────────────────────────────────────────

@patch("services.user_service.User.get")
@patch("services.user_service.approve_user")
def test_api_approve_user(mock_approve, mock_get):
    global active_user
    active_user = mock_owner
    
    user = MagicMock(spec=User)
    user.telegram_id = 123
    mock_get.return_value = user
    
    uid = PydanticObjectId()
    response = client.post("/api/admin/users/approve", json={"user_doc_id": str(uid)})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

# ── 16. POST /api/admin/users/revoke ───────────────────────────────────────────

@patch("services.user_service.User.get")
@patch("services.user_service.revoke_user")
def test_api_revoke_user(mock_revoke, mock_get):
    global active_user
    active_user = mock_owner
    
    user = MagicMock(spec=User)
    user.telegram_id = 123
    mock_get.return_value = user
    
    uid = PydanticObjectId()
    response = client.post("/api/admin/users/revoke", json={"user_doc_id": str(uid)})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

# ── 17. POST /api/admin/users/exceptions/allow ───────────────────────────────

@patch("services.user_service.User.get")
@patch("services.user_service.allow_folder_for_user")
def test_api_allow_exception(mock_allow, mock_get):
    global active_user
    active_user = mock_owner
    
    user = MagicMock(spec=User)
    mock_get.return_value = user
    
    uid = PydanticObjectId()
    fid = PydanticObjectId()
    response = client.post("/api/admin/users/exceptions/allow", json={"user_doc_id": str(uid), "folder_id": str(fid)})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

# ── 18. POST /api/admin/users/exceptions/block ───────────────────────────────

@patch("services.user_service.User.get")
@patch("services.user_service.block_folder_for_user")
def test_api_block_exception(mock_block, mock_get):
    global active_user
    active_user = mock_owner
    
    user = MagicMock(spec=User)
    mock_get.return_value = user
    
    uid = PydanticObjectId()
    fid = PydanticObjectId()
    response = client.post("/api/admin/users/exceptions/block", json={"user_doc_id": str(uid), "folder_id": str(fid)})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

# ── 19. POST /api/admin/users/exceptions/remove ──────────────────────────────

@patch("services.user_service.User.get")
def test_api_remove_exception(mock_get):
    global active_user
    active_user = mock_owner
    
    user = MagicMock(spec=User)
    fid = PydanticObjectId()
    user.allowed_folders = [fid]
    user.blocked_folders = []
    user.save = AsyncMock()
    mock_get.return_value = user
    
    uid = PydanticObjectId()
    response = client.post("/api/admin/users/exceptions/remove", json={"user_doc_id": str(uid), "folder_id": str(fid)})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

# ── 20. GET /api/admin/stats ───────────────────────────────────────────────────

@patch("bot.api.User")
@patch("bot.api.File")
@patch("bot.api.Folder")
def test_api_get_stats(mock_folder_class, mock_file_class, mock_user_class):
    global active_user
    active_user = mock_owner
    
    mock_folder_class.count = AsyncMock(return_value=5)
    mock_file_class.count = AsyncMock(return_value=10)
    
    # Mock aggregation results
    mock_total_size_query = MagicMock()
    mock_total_size_query.to_list = AsyncMock(return_value=[{"_id": None, "total_size": 100000}])
    
    mock_type_query = MagicMock()
    mock_type_query.to_list = AsyncMock(return_value=[{"_id": "video", "count": 8, "size": 90000}])
    
    mock_file_class.aggregate.side_effect = [mock_total_size_query, mock_type_query]
    
    # Mock user query calls
    mock_user_class.count = AsyncMock(return_value=15)
    mock_user_class.find.return_value.count = AsyncMock(side_effect=[5, 8, 2])
    
    response = client.get("/api/admin/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["folders_count"] == 5
    assert data["files_count"] == 10
    assert data["total_size"] == 100000
    assert data["file_types"]["video"]["count"] == 8
    assert data["file_types"]["video"]["size"] == 90000
    assert data["users"]["total"] == 15
    assert data["users"]["approved"] == 5

# ── 21. POST /api/admin/health-check ──────────────────────────────────────────

@patch("bot.api.BotSettings")
@patch("bot.api.File")
@patch("bot.api.tg_bot.get_messages", new_callable=AsyncMock)
@patch("services.folder_service.get_breadcrumbs")
def test_api_health_check(mock_breadcrumbs, mock_get_messages, mock_file_class, mock_settings_class):
    global active_user
    active_user = mock_owner
    
    mock_settings_class.get_dump_chat_id = AsyncMock(return_value=-100123456789)
    
    f = MagicMock()
    f.id = PydanticObjectId()
    f.name = "broken.mp4"
    f.dump_message_id = 99
    f.folder_id = PydanticObjectId()
    mock_file_class.find_all.return_value.to_list = AsyncMock(return_value=[f])
    
    # Mock Telegram message not found (broken link)
    msg_mock = MagicMock()
    msg_mock.empty = True
    mock_get_messages.return_value = [msg_mock]
    
    mock_breadcrumbs.return_value = []
    
    response = client.post("/api/admin/health-check")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["broken"]) == 1

# ── 22. POST /api/admin/purge-broken ───────────────────────────────────────────

@patch("services.file_service.delete_file")
def test_api_purge_broken(mock_delete):
    global active_user
    active_user = mock_owner
    mock_delete.return_value = True
    
    fid = PydanticObjectId()
    response = client.post("/api/admin/purge-broken", json={"file_ids": [str(fid)]})
    assert response.status_code == 200
    assert response.json()["purged_count"] == 1

# ── 23. GET /api/admin/folders/all ──────────────────────────────────────────
@patch("bot.api.Folder")
def test_api_get_all_folders(mock_folder_class):
    global active_user
    active_user = mock_owner
    
    fld = MagicMock()
    fld.id = PydanticObjectId()
    fld.name = "RootFolder"
    
    mock_folder_class.find_all.return_value.sort.return_value.to_list = AsyncMock(return_value=[fld])
    
    response = client.get("/api/admin/folders/all")
    assert response.status_code == 200
    assert len(response.json()) == 1

# ── 24. API Error Responses (Not Found & Validation Paths) ───────────────────

@patch("services.folder_service.get_folder")
def test_api_get_folders_not_found(mock_get_folder):
    mock_get_folder.return_value = None
    fid = PydanticObjectId()
    
    response = client.get(f"/api/folders?folder_id={fid}")
    assert response.status_code == 404

@patch("services.folder_service.create_folder")
def test_api_create_folder_conflict_or_error(mock_create):
    global active_user
    active_user = mock_owner
    mock_create.side_effect = ValueError("Folder name already exists here")
    
    response = client.post("/api/folders/create", json={"name": "Duplicate Folder", "parent_id": None})
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]

@patch("services.folder_service.rename_folder")
def test_api_rename_folder_not_found_or_conflict(mock_rename):
    global active_user
    active_user = mock_owner
    
    # Not found case
    mock_rename.return_value = None
    fid = PydanticObjectId()
    response = client.post("/api/folders/rename", json={"folder_id": str(fid), "new_name": "New Name"})
    assert response.status_code == 404
    
    # Conflict case (ValueError)
    mock_rename.side_effect = ValueError("Conflict")
    response = client.post("/api/folders/rename", json={"folder_id": str(fid), "new_name": "New Name"})
    assert response.status_code == 400

@patch("services.folder_service.delete_folder_tree")
def test_api_delete_folder_error(mock_delete):
    global active_user
    active_user = mock_owner
    mock_delete.side_effect = ValueError("Delete error")
    
    fid = PydanticObjectId()
    response = client.post("/api/folders/delete", json={"folder_id": str(fid)})
    assert response.status_code == 500

@patch("services.folder_service.move_folder")
def test_api_move_folder_error(mock_move):
    global active_user
    active_user = mock_owner
    mock_move.side_effect = ValueError("Move error")
    
    fid = PydanticObjectId()
    pid = PydanticObjectId()
    response = client.post("/api/folders/move", json={"folder_id": str(fid), "target_parent_id": str(pid)})
    assert response.status_code == 400

@patch("services.folder_service.copy_folder")
def test_api_copy_folder_error(mock_copy):
    global active_user
    active_user = mock_owner
    mock_copy.side_effect = ValueError("Copy error")
    
    fid = PydanticObjectId()
    pid = PydanticObjectId()
    response = client.post("/api/folders/copy", json={"folder_id": str(fid), "target_parent_id": str(pid)})
    assert response.status_code == 400

@patch("services.file_service.rename_file")
def test_api_rename_file_error(mock_rename):
    global active_user
    active_user = mock_owner
    
    # Not found case
    mock_rename.return_value = None
    fid = PydanticObjectId()
    response = client.post("/api/files/rename", json={"file_id": str(fid), "new_name": "New Name"})
    assert response.status_code == 404

@patch("services.file_service.delete_file")
def test_api_delete_file_not_found(mock_delete):
    global active_user
    active_user = mock_owner
    mock_delete.return_value = False
    
    fid = PydanticObjectId()
    response = client.post("/api/files/delete", json={"file_id": str(fid)})
    assert response.status_code == 404

@patch("services.user_service.has_file_access")
@patch("services.file_service.get_file")
@patch("handlers.playback._build_caption")
@patch("bot.api.tg_bot.send_video", new_callable=AsyncMock)
def test_api_play_file_errors(mock_send_video, mock_caption, mock_get_file, mock_has_file):
    mock_has_file.return_value = True
    fid = PydanticObjectId()
    mock_caption.return_value = "Caption"
    
    # Not found
    mock_get_file.return_value = None
    response = client.post("/api/files/play", json={"file_id": str(fid)})
    assert response.status_code == 404
    
    # Delivery failure
    fl = MagicMock()
    fl.id = fid
    fl.folder_id = PydanticObjectId()
    fl.file_type = "video"
    fl.file_id = "tg_video_id"
    mock_get_file.return_value = fl
    mock_send_video.side_effect = Exception("Telegram send failed")
    response = client.post("/api/files/play", json={"file_id": str(fid)})
    assert response.status_code == 500
    assert "Playback delivery failed" in response.json()["detail"]

@patch("services.file_service.move_file")
def test_api_move_file_errors(mock_move):
    global active_user
    active_user = mock_owner
    fid = PydanticObjectId()
    pid = PydanticObjectId()
    
    # Not found
    mock_move.return_value = None
    response = client.post("/api/files/move", json={"file_id": str(fid), "target_folder_id": str(pid)})
    assert response.status_code == 404

@patch("services.file_service.copy_file")
def test_api_copy_file_errors(mock_copy):
    global active_user
    active_user = mock_owner
    fid = PydanticObjectId()
    pid = PydanticObjectId()
    
    # Not found
    mock_copy.return_value = None
    response = client.post("/api/files/copy", json={"file_id": str(fid), "target_folder_id": str(pid)})
    assert response.status_code == 404

@patch("services.user_service.find_user_by_id_doc")
def test_api_admin_users_not_found_errors(mock_find_user):
    global active_user
    active_user = mock_owner
    mock_find_user.return_value = None
    uid = PydanticObjectId()
    fid = PydanticObjectId()
    
    # approve
    response = client.post("/api/admin/users/approve", json={"user_doc_id": str(uid)})
    assert response.status_code == 404
    
    # revoke
    response = client.post("/api/admin/users/revoke", json={"user_doc_id": str(uid)})
    assert response.status_code == 404
    
    # reset
    response = client.post("/api/admin/users/exceptions/reset", json={"user_doc_id": str(uid)})
    assert response.status_code == 404
    
    # allow
    response = client.post("/api/admin/users/exceptions/allow", json={"user_doc_id": str(uid), "folder_id": str(fid)})
    assert response.status_code == 404
    
    # block
    response = client.post("/api/admin/users/exceptions/block", json={"user_doc_id": str(uid), "folder_id": str(fid)})
    assert response.status_code == 404

# ── Extra API Coverage Tests ──────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("bot.api.verify_telegram_init_data")
async def test_get_current_user_no_id(mock_verify):
    mock_verify.return_value = (True, {"first_name": "No ID User"})
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(x_telegram_init_data="some_init_data")
    assert exc_info.value.status_code == 401
    assert "Invalid user data structure" in exc_info.value.detail

def test_api_invalid_objectid_handling():
    global active_user
    active_user = mock_owner
    
    # 1. /api/folders/size
    response = client.get("/api/folders/size?folder_id=invalid-id")
    assert response.status_code == 400
    
    # 2. /api/folders/create with invalid parent_id
    response = client.post("/api/folders/create", json={"name": "new", "parent_id": "invalid-id"})
    assert response.status_code == 400
    
    # 3. /api/folders/rename
    response = client.post("/api/folders/rename", json={"folder_id": "invalid-id", "new_name": "new"})
    assert response.status_code == 400
    
    # 4. /api/folders/delete
    response = client.post("/api/folders/delete", json={"folder_id": "invalid-id"})
    assert response.status_code == 400
    
    # 5. /api/folders/move
    response = client.post("/api/folders/move", json={"folder_id": "invalid-id", "target_parent_id": "root"})
    assert response.status_code == 400
    response = client.post("/api/folders/move", json={"folder_id": str(PydanticObjectId()), "target_parent_id": "invalid-id"})
    assert response.status_code == 400
    
    # 6. /api/folders/copy
    response = client.post("/api/folders/copy", json={"folder_id": "invalid-id", "target_parent_id": "root"})
    assert response.status_code == 400
    response = client.post("/api/folders/copy", json={"folder_id": str(PydanticObjectId()), "target_parent_id": "invalid-id"})
    assert response.status_code == 400

    # 7. /api/files/move
    response = client.post("/api/files/move", json={"file_id": "invalid-id", "target_folder_id": "root"})
    assert response.status_code == 400
    response = client.post("/api/files/move", json={"file_id": str(PydanticObjectId()), "target_folder_id": "invalid-id"})
    assert response.status_code == 400

    # 8. /api/files/copy
    response = client.post("/api/files/copy", json={"file_id": "invalid-id", "target_folder_id": "root"})
    assert response.status_code == 400
    response = client.post("/api/files/copy", json={"file_id": str(PydanticObjectId()), "target_folder_id": "invalid-id"})
    assert response.status_code == 400

    # 9. /api/files/rename
    response = client.post("/api/files/rename", json={"file_id": "invalid-id", "new_name": "new"})
    assert response.status_code == 400

    # 10. /api/files/delete
    response = client.post("/api/files/delete", json={"file_id": "invalid-id"})
    assert response.status_code == 400

    # 11. /api/files/play
    response = client.post("/api/files/play", json={"file_id": "invalid-id"})
    assert response.status_code == 400

    # 12. /api/admin/users/exceptions/allow
    response = client.post("/api/admin/users/exceptions/allow", json={"user_doc_id": str(PydanticObjectId()), "folder_id": "invalid-id"})
    assert response.status_code == 400

    # 13. /api/admin/users/exceptions/block
    response = client.post("/api/admin/users/exceptions/block", json={"user_doc_id": str(PydanticObjectId()), "folder_id": "invalid-id"})
    assert response.status_code == 400

@patch("services.folder_service.delete_folder_tree")
def test_api_delete_folder_exception(mock_delete_tree):
    global active_user
    active_user = mock_owner
    mock_delete_tree.side_effect = Exception("database error")
    
    response = client.post("/api/folders/delete", json={"folder_id": str(PydanticObjectId())})
    assert response.status_code == 500
    assert "Internal deletion error" in response.json()["detail"]

@patch("services.user_service.has_file_access")
@patch("services.file_service.get_file")
@patch("handlers.playback._build_caption")
@patch("bot.api.tg_bot.send_photo", new_callable=AsyncMock)
@patch("bot.api.tg_bot.send_document", new_callable=AsyncMock)
@patch("bot.api.settings")
@patch("bot.api.schedule_auto_delete", new_callable=AsyncMock)
def test_api_play_file_types(mock_schedule_delete, mock_settings, mock_send_doc, mock_send_photo, mock_caption, mock_get_file, mock_has_file):
    global active_user
    active_user = mock_approved
    mock_has_file.return_value = True
    mock_caption.return_value = "Caption"
    mock_settings.auto_delete_hours = 2
    mock_settings.protect_content = True
    
    # 1. Play Photo
    photo_file = MagicMock()
    photo_file.id = PydanticObjectId()
    photo_file.folder_id = PydanticObjectId()
    photo_file.file_type = "photo"
    photo_file.file_id = "tg_photo_id"
    mock_get_file.return_value = photo_file
    
    response = client.post("/api/files/play", json={"file_id": str(photo_file.id)})
    assert response.status_code == 200
    mock_send_photo.assert_called_once()
    
    # 2. Play Document
    doc_file = MagicMock()
    doc_file.id = PydanticObjectId()
    doc_file.folder_id = PydanticObjectId()
    doc_file.file_type = "document"
    doc_file.file_id = "tg_doc_id"
    mock_get_file.return_value = doc_file
    
    response = client.post("/api/files/play", json={"file_id": str(doc_file.id)})
    assert response.status_code == 200
    mock_send_doc.assert_called_once()

@patch("bot.api.User")
@patch("models.folder.Folder.get")
def test_api_admin_users_missing_folders(mock_folder_get, mock_user_class):
    global active_user
    active_user = mock_owner
    
    user1 = MagicMock()
    user1.id = PydanticObjectId()
    user1.telegram_id = 111
    user1.display_name = "User One"
    user1.username = "userone"
    user1.role = UserRole.APPROVED
    user1.approved_at = None
    user1.allowed_folders = [PydanticObjectId()]
    user1.blocked_folders = [PydanticObjectId()]
    
    # Mock find().sort().to_list()
    mock_user_class.find.return_value.sort.return_value.to_list = AsyncMock(return_value=[user1])
    
    # Folder.get returns None (missing folder)
    mock_folder_get.return_value = None
    
    response = client.get("/api/admin/users")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["allowed_folders"] == []
    assert data[0]["blocked_folders"] == []
