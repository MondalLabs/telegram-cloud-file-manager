import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from beanie import PydanticObjectId
from models.user import User, UserRole
from services.user_service import (
    get_or_create,
    get_role,
    approve_user,
    revoke_user,
    list_approved,
    count_approved,
    get_approved_paginated,
    find_user_by_id,
    find_user_by_id_doc,
    allow_folder_for_user,
    block_folder_for_user,
    reset_folder_permissions_for_user,
    has_file_access,
    has_folder_access
)

@pytest.mark.asyncio
@patch("services.user_service.User")
@patch("services.user_service.cfg")
async def test_get_or_create_new_guest(mock_cfg, mock_user_class):
    mock_cfg.owner_id = 999
    mock_user_class.find_one = AsyncMock(return_value=None)
    
    mock_user_instance = MagicMock()
    mock_user_instance.insert = AsyncMock()
    mock_user_class.return_value = mock_user_instance

    res = await get_or_create(telegram_id=123, full_name="John Doe", username="johndoe")
    assert res == mock_user_instance
    mock_user_class.assert_called_once()
    mock_user_instance.insert.assert_called_once()

@pytest.mark.asyncio
@patch("services.user_service.User")
@patch("services.user_service.cfg")
async def test_get_or_create_new_owner(mock_cfg, mock_user_class):
    mock_cfg.owner_id = 999
    mock_user_class.find_one = AsyncMock(return_value=None)
    
    mock_user_instance = MagicMock()
    mock_user_instance.insert = AsyncMock()
    mock_user_class.return_value = mock_user_instance

    res = await get_or_create(telegram_id=999, full_name="Owner", username="owner")
    assert res == mock_user_instance
    mock_user_class.assert_called_once()

@pytest.mark.asyncio
@patch("services.user_service.User")
@patch("services.user_service.cfg")
async def test_get_or_create_existing_update(mock_cfg, mock_user_class):
    mock_cfg.owner_id = 999
    
    existing_user = MagicMock()
    existing_user.telegram_id = 123
    existing_user.full_name = "Old Name"
    existing_user.username = "olduser"
    existing_user.role = UserRole.APPROVED
    existing_user.save = AsyncMock()
    
    mock_user_class.find_one = AsyncMock(return_value=existing_user)

    res = await get_or_create(telegram_id=123, full_name="New Name", username="newuser")
    assert res == existing_user
    assert existing_user.full_name == "New Name"
    assert existing_user.username == "newuser"
    existing_user.save.assert_called_once()

@pytest.mark.asyncio
@patch("services.user_service.User")
@patch("services.user_service.cfg")
async def test_get_or_create_existing_tampered_owner(mock_cfg, mock_user_class):
    mock_cfg.owner_id = 999
    
    existing_user = MagicMock()
    existing_user.telegram_id = 999
    existing_user.full_name = "Owner"
    existing_user.username = "owner"
    existing_user.role = UserRole.GUEST  # Tampered role
    existing_user.save = AsyncMock()
    
    mock_user_class.find_one = AsyncMock(return_value=existing_user)

    res = await get_or_create(telegram_id=999, full_name="Owner", username="owner")
    assert res.role == UserRole.OWNER
    existing_user.save.assert_called_once()

@pytest.mark.asyncio
@patch("services.user_service.User")
async def test_get_role_exists(mock_user_class):
    user = MagicMock()
    user.role = UserRole.APPROVED
    mock_user_class.find_one = AsyncMock(return_value=user)
    
    role = await get_role(123)
    assert role == UserRole.APPROVED

@pytest.mark.asyncio
@patch("services.user_service.User")
async def test_get_role_not_exists(mock_user_class):
    mock_user_class.find_one = AsyncMock(return_value=None)
    role = await get_role(123)
    assert role == UserRole.GUEST

@pytest.mark.asyncio
@patch("services.user_service.User")
async def test_approve_user_success(mock_user_class):
    user = MagicMock()
    user.role = UserRole.GUEST
    user.save = AsyncMock()
    mock_user_class.find_one = AsyncMock(return_value=user)
    
    res = await approve_user(123, approved_by=999)
    assert res == user
    assert user.role == UserRole.APPROVED
    user.save.assert_called_once()

@pytest.mark.asyncio
@patch("services.user_service.User")
async def test_approve_user_not_found(mock_user_class):
    mock_user_class.find_one = AsyncMock(return_value=None)
    res = await approve_user(123, approved_by=999)
    assert res is None

@pytest.mark.asyncio
@patch("services.user_service.User")
async def test_approve_user_owner_error(mock_user_class):
    user = MagicMock()
    user.role = UserRole.OWNER
    mock_user_class.find_one = AsyncMock(return_value=user)
    
    with pytest.raises(ValueError, match="Cannot change the role of the bot owner."):
        await approve_user(123, approved_by=999)

@pytest.mark.asyncio
@patch("services.user_service.User")
async def test_revoke_user_success(mock_user_class):
    user = MagicMock()
    user.role = UserRole.APPROVED
    user.save = AsyncMock()
    mock_user_class.find_one = AsyncMock(return_value=user)
    
    res = await revoke_user(123)
    assert res == user
    assert user.role == UserRole.GUEST
    user.save.assert_called_once()

@pytest.mark.asyncio
@patch("services.user_service.User")
async def test_revoke_user_owner_error(mock_user_class):
    user = MagicMock()
    user.role = UserRole.OWNER
    mock_user_class.find_one = AsyncMock(return_value=user)
    
    with pytest.raises(ValueError, match="Cannot revoke the bot owner's access."):
        await revoke_user(123)

@pytest.mark.asyncio
@patch("services.user_service.User")
async def test_revoke_user_not_found(mock_user_class):
    mock_user_class.find_one = AsyncMock(return_value=None)
    res = await revoke_user(123)
    assert res is None

@pytest.mark.asyncio
@patch("services.user_service.User")
async def test_list_approved(mock_user_class):
    find_mock = MagicMock()
    find_mock.sort.return_value.to_list = AsyncMock(return_value=[])
    mock_user_class.find = MagicMock(return_value=find_mock)
    
    res = await list_approved()
    assert res == []

@pytest.mark.asyncio
@patch("services.user_service.User")
async def test_count_approved(mock_user_class):
    find_mock = MagicMock()
    find_mock.count = AsyncMock(return_value=5)
    mock_user_class.find = MagicMock(return_value=find_mock)
    
    res = await count_approved()
    assert res == 5

@pytest.mark.asyncio
@patch("services.user_service.User")
async def test_get_approved_paginated(mock_user_class):
    find_mock = MagicMock()
    sort_mock = MagicMock()
    skip_mock = MagicMock()
    limit_mock = MagicMock()
    
    find_mock.sort.return_value = sort_mock
    sort_mock.skip.return_value = skip_mock
    skip_mock.limit.return_value = limit_mock
    limit_mock.to_list = AsyncMock(return_value=[])
    
    mock_user_class.find = MagicMock(return_value=find_mock)
    
    res = await get_approved_paginated(skip=10, limit=5)
    assert res == []

@pytest.mark.asyncio
@patch("services.user_service.User")
async def test_find_user_by_id(mock_user_class):
    mock_user_class.find_one = AsyncMock(return_value=None)
    res = await find_user_by_id(123)
    assert res is None

@pytest.mark.asyncio
@patch("services.user_service.User")
async def test_find_user_by_id_doc_success(mock_user_class):
    user_id = PydanticObjectId()
    mock_user_class.get = AsyncMock(return_value=None)
    res = await find_user_by_id_doc(str(user_id))
    assert res is None

@pytest.mark.asyncio
@patch("services.user_service.User")
async def test_find_user_by_id_doc_invalid(mock_user_class):
    res = await find_user_by_id_doc("invalid_id")
    assert res is None

@pytest.mark.asyncio
async def test_allow_folder_for_user():
    user = MagicMock()
    user.allowed_folders = []
    user.blocked_folders = []
    user.save = AsyncMock()
    
    folder_id = PydanticObjectId()
    
    # 1. Allow folder
    await allow_folder_for_user(user, folder_id)
    assert folder_id in user.allowed_folders
    user.save.assert_called_once()
    
    # 2. Block folder (clears it from allowed)
    user.save.reset_mock()
    await block_folder_for_user(user, folder_id)
    assert folder_id not in user.allowed_folders
    assert folder_id in user.blocked_folders
    user.save.assert_called_once()

@pytest.mark.asyncio
async def test_reset_folder_permissions_for_user():
    user = MagicMock()
    user.allowed_folders = [PydanticObjectId()]
    user.blocked_folders = [PydanticObjectId()]
    user.save = AsyncMock()
    
    await reset_folder_permissions_for_user(user)
    assert len(user.allowed_folders) == 0
    assert len(user.blocked_folders) == 0

@pytest.mark.asyncio
@patch("services.user_service.User")
@patch("services.user_service.cfg")
async def test_get_or_create_existing_no_update(mock_cfg, mock_user_class):
    mock_cfg.owner_id = 999
    
    existing_user = MagicMock()
    existing_user.telegram_id = 123
    existing_user.full_name = "Same Name"
    existing_user.username = "sameuser"
    existing_user.role = UserRole.APPROVED
    existing_user.save = AsyncMock()
    
    mock_user_class.find_one = AsyncMock(return_value=existing_user)

    res = await get_or_create(telegram_id=123, full_name="Same Name", username="sameuser")
    assert res == existing_user
    existing_user.save.assert_not_called()

@pytest.mark.asyncio
@patch("services.folder_service.get_folder")
async def test_has_file_access_missing_parent_folder(mock_get_folder):
    user = MagicMock()
    user.role = UserRole.APPROVED
    user.allowed_folders = [PydanticObjectId()]
    user.blocked_folders = []
    
    mock_get_folder.return_value = None
    
    fid = PydanticObjectId()
    res = await has_file_access(user, fid)
    assert res is False

@pytest.mark.asyncio
@patch("services.folder_service.get_folder")
async def test_has_folder_access_missing_parent_folder(mock_get_folder):
    user = MagicMock()
    user.role = UserRole.APPROVED
    user.allowed_folders = [PydanticObjectId()]
    user.blocked_folders = []
    
    mock_get_folder.return_value = None
    
    fid = PydanticObjectId()
    res = await has_folder_access(user, fid)
    assert res is False

@pytest.mark.asyncio
async def test_allow_and_block_folder_extra_branches():
    user = MagicMock()
    folder_id = PydanticObjectId()
    user.save = AsyncMock()
    
    user.blocked_folders = [folder_id]
    user.allowed_folders = []
    await allow_folder_for_user(user, folder_id)
    assert folder_id not in user.blocked_folders
    assert folder_id in user.allowed_folders
    
    user.allowed_folders = []
    user.blocked_folders = []
    await block_folder_for_user(user, folder_id)
    assert folder_id in user.blocked_folders
