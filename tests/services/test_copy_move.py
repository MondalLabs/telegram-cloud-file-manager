import pytest
from unittest.mock import AsyncMock, MagicMock
from beanie import PydanticObjectId
from services.folder_service import move_folder, copy_folder
from services.file_service import move_file, copy_file

@pytest.mark.asyncio
async def test_move_folder_cycle_detection(mocker):
    # Mock Folder class
    mock_folder_class = mocker.patch("services.folder_service.Folder")
    
    # Create target parent and source folder mock instances
    source_folder_id = PydanticObjectId()
    target_parent_id = PydanticObjectId()
    
    source_folder = AsyncMock()
    source_folder.id = source_folder_id
    source_folder.name = "Source"
    source_folder.parent_id = None
    
    target_parent = AsyncMock()
    target_parent.id = target_parent_id
    target_parent.name = "Target"
    target_parent.parent_id = source_folder_id  # Target's parent is source_folder, which forms a cycle!
    
    async def get_mock_folder(fid):
        if fid == source_folder_id:
            return source_folder
        if fid == target_parent_id:
            return target_parent
        return None
        
    mock_folder_class.get = AsyncMock(side_effect=get_mock_folder)
    
    with pytest.raises(ValueError, match="Cannot move a folder into itself or one of its subfolders."):
        await move_folder(source_folder_id, target_parent_id)

@pytest.mark.asyncio
async def test_move_folder_success(mocker):
    mock_folder_class = mocker.patch("services.folder_service.Folder")
    
    source_folder_id = PydanticObjectId()
    target_parent_id = PydanticObjectId()
    
    source_folder = AsyncMock()
    source_folder.id = source_folder_id
    source_folder.name = "Source"
    source_folder.parent_id = None
    
    target_parent = AsyncMock()
    target_parent.id = target_parent_id
    target_parent.name = "Target"
    target_parent.parent_id = None
    
    async def get_mock_folder(fid):
        if fid == source_folder_id:
            return source_folder
        if fid == target_parent_id:
            return target_parent
        return None
        
    mock_folder_class.get = AsyncMock(side_effect=get_mock_folder)
    mock_folder_class.find_one = AsyncMock(return_value=None)  # No name conflict
    
    res = await move_folder(source_folder_id, target_parent_id)
    assert res.parent_id == target_parent_id
    source_folder.save.assert_called_once()
