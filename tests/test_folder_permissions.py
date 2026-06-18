import pytest
from unittest.mock import AsyncMock, patch
from beanie import PydanticObjectId
from models.user import UserRole
from services.user_service import has_folder_access

class FakeUser:
    def __init__(self, telegram_id, role, allowed_folders=None, blocked_folders=None):
        self.telegram_id = telegram_id
        self.role = role
        self.allowed_folders = allowed_folders or []
        self.blocked_folders = blocked_folders or []

class FakeFolder:
    def __init__(self, name, parent_id):
        self.name = name
        self.parent_id = parent_id

@pytest.mark.anyio
@patch("services.folder_service.get_folder")
async def test_has_folder_access_owner(mock_get_folder):
    # Owner has access to everything
    owner = FakeUser(telegram_id=123, role=UserRole.OWNER)
    assert await has_folder_access(owner, PydanticObjectId()) is True

@pytest.mark.anyio
@patch("services.folder_service.get_folder")
async def test_has_folder_access_root(mock_get_folder):
    # Approved user has access to root by default
    user = FakeUser(telegram_id=123, role=UserRole.APPROVED)
    assert await has_folder_access(user, None) is True

@pytest.mark.anyio
@patch("services.folder_service.get_folder")
async def test_has_folder_access_default_allowed(mock_get_folder):
    # Approved user with no explicit allows or blocks has access to folders by default
    user = FakeUser(telegram_id=123, role=UserRole.APPROVED, allowed_folders=[], blocked_folders=[])
    folder_id = PydanticObjectId()
    
    # Mock folder has no parent (root level child)
    mock_get_folder.return_value = FakeFolder(name="test", parent_id=None)
    
    assert await has_folder_access(user, folder_id) is True

@pytest.mark.anyio
@patch("services.folder_service.get_folder")
async def test_has_folder_access_explicit_block(mock_get_folder):
    folder_id = PydanticObjectId()
    user = FakeUser(
        telegram_id=123,
        role=UserRole.APPROVED,
        allowed_folders=[],
        blocked_folders=[folder_id]
    )
    
    mock_get_folder.return_value = FakeFolder(name="test", parent_id=None)
    
    # Target folder is blocked
    assert await has_folder_access(user, folder_id) is False

@pytest.mark.anyio
@patch("services.folder_service.get_folder")
async def test_has_folder_access_explicit_allow(mock_get_folder):
    allowed_id = PydanticObjectId()
    other_id = PydanticObjectId()
    user = FakeUser(
        telegram_id=123,
        role=UserRole.APPROVED,
        allowed_folders=[allowed_id],
        blocked_folders=[]
    )
    
    mock_get_folder.return_value = FakeFolder(name="test", parent_id=None)
    
    # Allowed folder is accessible
    assert await has_folder_access(user, allowed_id) is True
    # Non-allowed folder is blocked (whitelist model)
    assert await has_folder_access(user, other_id) is False

@pytest.mark.anyio
@patch("services.folder_service.get_folder")
async def test_has_folder_access_ancestor_block(mock_get_folder):
    parent_id = PydanticObjectId()
    child_id = PydanticObjectId()
    
    user = FakeUser(
        telegram_id=123,
        role=UserRole.APPROVED,
        allowed_folders=[],
        blocked_folders=[parent_id]
    )
    
    parent_folder = FakeFolder(name="Parent", parent_id=None)
    child_folder = FakeFolder(name="Child", parent_id=parent_id)
    
    # Mock folder chain resolution
    async def get_mock_folder(fid):
        if fid == child_id:
            return child_folder
        if fid == parent_id:
            return parent_folder
        return None
        
    mock_get_folder.side_effect = get_mock_folder
    
    # Child is blocked because parent is blocked
    assert await has_folder_access(user, child_id) is False
