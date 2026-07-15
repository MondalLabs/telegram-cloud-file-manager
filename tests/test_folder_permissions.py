import pytest
from unittest.mock import AsyncMock, patch
from beanie import PydanticObjectId
from models.user import UserRole
from services.user_service import has_folder_access, has_file_access

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
async def test_owner_access(mock_get_folder):
    # Owner has folder and file access to everything
    owner = FakeUser(telegram_id=123, role=UserRole.OWNER)
    assert await has_folder_access(owner, PydanticObjectId()) is True
    assert await has_file_access(owner, PydanticObjectId()) is True

@pytest.mark.anyio
@patch("services.folder_service.get_folder")
async def test_root_access(mock_get_folder):
    # Approved user has access to root folder by default
    user_default = FakeUser(telegram_id=123, role=UserRole.APPROVED)
    assert await has_folder_access(user_default, None) is True
    assert await has_file_access(user_default, None) is True

    # If allowed_folders is active, root is navigable but files in root are hidden/blocked
    user_whitelist = FakeUser(
        telegram_id=123,
        role=UserRole.APPROVED,
        allowed_folders=[PydanticObjectId()]
    )
    assert await has_folder_access(user_whitelist, None) is True
    assert await has_file_access(user_whitelist, None) is False

@pytest.mark.anyio
@patch("services.folder_service.get_folder")
async def test_default_allowed_no_exceptions(mock_get_folder):
    # Approved user with no explicit allows or blocks has access to folders and files by default
    user = FakeUser(telegram_id=123, role=UserRole.APPROVED, allowed_folders=[], blocked_folders=[])
    folder_id = PydanticObjectId()
    
    mock_get_folder.return_value = FakeFolder(name="test", parent_id=None)
    
    assert await has_folder_access(user, folder_id) is True
    assert await has_file_access(user, folder_id) is True

@pytest.mark.anyio
@patch("services.folder_service.get_folder")
async def test_explicit_block(mock_get_folder):
    folder_id = PydanticObjectId()
    user = FakeUser(
        telegram_id=123,
        role=UserRole.APPROVED,
        allowed_folders=[],
        blocked_folders=[folder_id]
    )
    
    mock_get_folder.return_value = FakeFolder(name="test", parent_id=None)
    
    assert await has_folder_access(user, folder_id) is False
    assert await has_file_access(user, folder_id) is False

@pytest.mark.anyio
@patch("services.folder_service.get_folder")
async def test_explicit_allow(mock_get_folder):
    allowed_id = PydanticObjectId()
    other_id = PydanticObjectId()
    user = FakeUser(
        telegram_id=123,
        role=UserRole.APPROVED,
        allowed_folders=[allowed_id],
        blocked_folders=[]
    )
    
    mock_get_folder.return_value = FakeFolder(name="test", parent_id=None)
    
    # Allowed folder is navigable and files inside it are accessible
    assert await has_folder_access(user, allowed_id) is True
    assert await has_file_access(user, allowed_id) is True
    
    # Other folder (not in allowed list) is neither navigable nor has file access
    assert await has_folder_access(user, other_id) is False
    assert await has_file_access(user, other_id) is False

@pytest.mark.anyio
@patch("services.folder_service.get_folder")
async def test_ancestor_block(mock_get_folder):
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
    
    async def get_mock_folder(fid):
        if fid == child_id:
            return child_folder
        if fid == parent_id:
            return parent_folder
        return None
        
    mock_get_folder.side_effect = get_mock_folder
    
    # Child is blocked because parent is blocked
    assert await has_folder_access(user, child_id) is False
    assert await has_file_access(user, child_id) is False

@pytest.mark.anyio
@patch("services.folder_service.get_folder")
async def test_scenario_1_blocked_parent_allowed_child(mock_get_folder):
    """
    Scenario 1: Parent is blocked, but child is explicitly allowed.
    Parent folder must be navigable (so user can reach child), but files in parent must be hidden.
    Child folder must be navigable and its files must be visible.
    """
    parent_id = PydanticObjectId()
    child_id = PydanticObjectId()
    
    user = FakeUser(
        telegram_id=123,
        role=UserRole.APPROVED,
        allowed_folders=[child_id],
        blocked_folders=[parent_id]
    )
    
    parent_folder = FakeFolder(name="Parent", parent_id=None)
    child_folder = FakeFolder(name="Child", parent_id=parent_id)
    
    async def get_mock_folder(fid):
        if fid == child_id:
            return child_folder
        if fid == parent_id:
            return parent_folder
        return None
        
    mock_get_folder.side_effect = get_mock_folder
    
    # Parent: navigable (True) but files hidden (False)
    assert await has_folder_access(user, parent_id) is True
    assert await has_file_access(user, parent_id) is False
    
    # Child: navigable (True) and files accessible (True - closest rule wins)
    assert await has_folder_access(user, child_id) is True
    assert await has_file_access(user, child_id) is True

@pytest.mark.anyio
@patch("services.folder_service.get_folder")
async def test_scenario_2_allowed_subfolder_default_parents(mock_get_folder):
    """
    Scenario 2: Only child is allowed (no blocks on parent).
    Parent folder must be navigable (so user can reach child), but files in parent must be hidden.
    Child folder must be navigable and its files must be visible.
    """
    parent_id = PydanticObjectId()
    child_id = PydanticObjectId()
    
    user = FakeUser(
        telegram_id=123,
        role=UserRole.APPROVED,
        allowed_folders=[child_id],
        blocked_folders=[]
    )
    
    parent_folder = FakeFolder(name="Parent", parent_id=None)
    child_folder = FakeFolder(name="Child", parent_id=parent_id)
    
    async def get_mock_folder(fid):
        if fid == child_id:
            return child_folder
        if fid == parent_id:
            return parent_folder
        return None
        
    mock_get_folder.side_effect = get_mock_folder
    
    # Parent: navigable (True) but files hidden (False - whitelist model default)
    assert await has_folder_access(user, parent_id) is True
    assert await has_file_access(user, parent_id) is False
    
    # Child: navigable (True) and files accessible (True)
    assert await has_folder_access(user, child_id) is True
    assert await has_file_access(user, child_id) is True
