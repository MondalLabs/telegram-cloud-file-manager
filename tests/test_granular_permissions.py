import pytest
from fastapi import FastAPI, HTTPException, Depends
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from beanie import PydanticObjectId

from bot.api import router, get_current_user, get_admin_user, require_permission
from models.user import User, UserRole
from models.folder import Folder
from models.file import File
from keyboards.navigation_kb import build_folder_keyboard, build_empty_folder_keyboard
from keyboards.admin_kb import folder_actions_kb, file_actions_kb
from utils.pagination import Page

# Setup Test App
app = FastAPI()
app.include_router(router)

# Mock users
mock_owner = MagicMock(spec=User)
mock_owner.role = UserRole.OWNER
mock_owner.telegram_id = 999

mock_approved = MagicMock(spec=User)
mock_approved.role = UserRole.APPROVED
mock_approved.telegram_id = 123
mock_approved.can_upload = False
mock_approved.can_create_folder = False
mock_approved.can_rename = False
mock_approved.can_delete = False
mock_approved.can_move_copy = False

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
    # Clear overrides properties
    mock_approved.can_upload = False
    mock_approved.can_create_folder = False
    mock_approved.can_rename = False
    mock_approved.can_delete = False
    mock_approved.can_move_copy = False


# ── 1. FastAPI REST API Gating Tests ───────────────────────────────────────────

@patch("services.folder_service.create_folder", new_callable=AsyncMock)
def test_create_folder_permissions(mock_create):
    global active_user
    folder_mock = MagicMock(spec=Folder)
    folder_mock.id = PydanticObjectId()
    folder_mock.name = "New Folder"
    mock_create.return_value = folder_mock

    # 1. Denied without permission
    response = client.post("/api/folders/create", json={"name": "New Folder", "parent_id": None})
    assert response.status_code == 403

    # 2. Allowed with permission
    mock_approved.can_create_folder = True
    response = client.post("/api/folders/create", json={"name": "New Folder", "parent_id": None})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    # 3. Owner bypasses check
    active_user = mock_owner
    response = client.post("/api/folders/create", json={"name": "New Folder", "parent_id": None})
    assert response.status_code == 200


@patch("services.folder_service.rename_folder", new_callable=AsyncMock)
def test_rename_folder_permissions(mock_rename):
    global active_user
    folder_mock = MagicMock(spec=Folder)
    folder_mock.id = PydanticObjectId()
    folder_mock.name = "Renamed"
    mock_rename.return_value = folder_mock

    fid = str(PydanticObjectId())
    
    # 1. Denied
    response = client.post("/api/folders/rename", json={"folder_id": fid, "new_name": "Renamed"})
    assert response.status_code == 403

    # 2. Allowed
    mock_approved.can_rename = True
    response = client.post("/api/folders/rename", json={"folder_id": fid, "new_name": "Renamed"})
    assert response.status_code == 200


@patch("services.folder_service.delete_folder_tree", new_callable=AsyncMock)
def test_delete_folder_permissions(mock_delete):
    global active_user
    mock_delete.return_value = {"folders_deleted": 1, "files_deleted": 2}

    fid = str(PydanticObjectId())
    
    # 1. Denied
    response = client.post("/api/folders/delete", json={"folder_id": fid})
    assert response.status_code == 403

    # 2. Allowed
    mock_approved.can_delete = True
    response = client.post("/api/folders/delete", json={"folder_id": fid})
    assert response.status_code == 200


@patch("services.folder_service.move_folder", new_callable=AsyncMock)
def test_move_folder_permissions(mock_move):
    global active_user
    folder_mock = MagicMock(spec=Folder)
    folder_mock.id = PydanticObjectId()
    folder_mock.name = "Moved"
    folder_mock.parent_id = None
    mock_move.return_value = folder_mock

    fid = str(PydanticObjectId())
    
    # 1. Denied
    response = client.post("/api/folders/move", json={"folder_id": fid, "target_parent_id": None})
    assert response.status_code == 403

    # 2. Allowed
    mock_approved.can_move_copy = True
    response = client.post("/api/folders/move", json={"folder_id": fid, "target_parent_id": None})
    assert response.status_code == 200


@patch("models.user.User.get", new_callable=AsyncMock)
def test_admin_permissions_update_gating(mock_user_get):
    global active_user
    target_user = MagicMock(spec=User)
    target_user.save = AsyncMock()
    mock_user_get.return_value = target_user

    payload = {
        "user_doc_id": str(PydanticObjectId()),
        "can_upload": True,
        "can_create_folder": True,
        "can_rename": False,
        "can_delete": False,
        "can_move_copy": True
    }

    # 1. Denied for approved user (Requires Super-Admin Owner role)
    response = client.post("/api/admin/users/permissions", json=payload)
    assert response.status_code == 403

    # 2. Approved for owner
    active_user = mock_owner
    response = client.post("/api/admin/users/permissions", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert target_user.can_upload is True
    assert target_user.can_create_folder is True
    assert target_user.can_move_copy is True
    target_user.save.assert_called_once()


# ── 2. Bot inline keyboard rendering checks ───────────────────────────────────

def test_navigation_keyboard_rendering():
    # Setup folders/files mock collections
    folder_a = MagicMock(spec=Folder, id=PydanticObjectId())
    folder_a.name = "Folder A"
    file_a = MagicMock(spec=File, id=PydanticObjectId())
    file_a.name = "File A"
    file_a.display_meta = "video"
    file_a.icon = "🎬"
    
    folders = [folder_a]
    files = [file_a]
    page_items = [("folder", folders[0]), ("file", files[0])]
    pg = Page(items=page_items, page=1, total_pages=1, total_items=2)

    # 1. Approved user with NO write permissions
    kb = build_folder_keyboard(pg, current_id="root", back_id=None, user=mock_approved)
    inline_kb = kb.inline_keyboard
    # Flatten buttons to audit labels and callbacks
    buttons = [btn for row in inline_kb for btn in row]
    
    # Non-owner with no write exceptions should NOT see ➕ New Folder, 📤 Upload, or ⚙️ actions
    assert not any(btn.text == "➕ New Folder" for btn in buttons)
    assert not any(btn.text == "📤 Upload" for btn in buttons)
    assert not any(btn.text == "⚙️" for btn in buttons)

    # 2. Approved user with can_create_folder exception
    mock_approved.can_create_folder = True
    kb = build_folder_keyboard(pg, current_id="root", back_id=None, user=mock_approved)
    buttons = [btn for row in kb.inline_keyboard for btn in row]
    assert any(btn.text == "➕ New Folder" for btn in buttons)
    assert not any(btn.text == "📤 Upload" for btn in buttons)
    assert not any(btn.text == "⚙️" for btn in buttons)

    # 3. Approved user with can_rename exception (should show gear buttons)
    mock_approved.can_create_folder = False
    mock_approved.can_rename = True
    kb = build_folder_keyboard(pg, current_id="root", back_id=None, user=mock_approved)
    buttons = [btn for row in kb.inline_keyboard for btn in row]
    assert any(btn.text == "⚙️" for btn in buttons)
    assert not any(btn.text == "➕ New Folder" for btn in buttons)


def test_action_menus_filtering():
    # Folder actions menu for user with rename & upload but no delete
    mock_approved.can_rename = True
    mock_approved.can_upload = True
    mock_approved.can_delete = False

    kb = folder_actions_kb(folder_id=str(PydanticObjectId()), parent_id="root", user=mock_approved)
    buttons = [btn for row in kb.inline_keyboard for btn in row]
    assert any(btn.text == "✏️ Rename" for btn in buttons)
    assert any(btn.text == "📤 Upload Here" for btn in buttons)
    assert not any(btn.text == "🗑️ Delete Folder" for btn in buttons)

    # File actions menu for user with delete but no rename
    mock_approved.can_rename = False
    mock_approved.can_delete = True
    kb = file_actions_kb(file_id=str(PydanticObjectId()), folder_id="root", user=mock_approved)
    buttons = [btn for row in kb.inline_keyboard for btn in row]
    assert not any(btn.text == "✏️ Rename" for btn in buttons)
    assert any(btn.text == "🗑️ Delete" for btn in buttons)
