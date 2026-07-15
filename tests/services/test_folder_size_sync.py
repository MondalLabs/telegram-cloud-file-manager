import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from beanie import PydanticObjectId
from services.folder_service import update_folder_size_hierarchy, recalculate_all_folder_sizes
from services.file_service import create_file, delete_file, move_file

@pytest.mark.asyncio
@patch("services.folder_service.Folder")
async def test_update_folder_size_hierarchy(mock_folder_class):
    parent_id = PydanticObjectId()
    child_id = PydanticObjectId()

    parent_folder = MagicMock()
    parent_folder.id = parent_id
    parent_folder.parent_id = None

    child_folder = MagicMock()
    child_folder.id = child_id
    child_folder.parent_id = parent_id

    async def get_mock_folder(fid):
        if fid == child_id:
            return child_folder
        if fid == parent_id:
            return parent_folder
        return None

    mock_folder_class.get = AsyncMock(side_effect=get_mock_folder)
    mock_collection = MagicMock()
    mock_collection.update_one = AsyncMock()
    mock_folder_class.get_pymongo_collection.return_value = mock_collection

    await update_folder_size_hierarchy(child_id, 500)

    # Verify that it walked up the ancestor tree and updated each document
    assert mock_collection.update_one.call_count == 2
    mock_collection.update_one.assert_any_call({"_id": child_id}, {"$inc": {"size": 500}})
    mock_collection.update_one.assert_any_call({"_id": parent_id}, {"$inc": {"size": 500}})

@pytest.mark.asyncio
@patch("services.file_service.File")
@patch("services.folder_service.update_folder_size_hierarchy")
async def test_create_file_updates_hierarchy(mock_update, mock_file_class):
    mock_file_instance = AsyncMock()
    mock_file_instance.file_size = 1000
    mock_file_instance.folder_id = PydanticObjectId()
    mock_file_class.return_value = mock_file_instance

    file_doc = await create_file(
        name="test.txt",
        file_id="tg_123",
        file_type="document",
        folder_id=mock_file_instance.folder_id,
        uploaded_by=123,
        file_size=1000
    )

    mock_file_instance.insert.assert_called_once()
    mock_update.assert_called_once_with(file_doc.folder_id, 1000)

@pytest.mark.asyncio
@patch("services.file_service.File")
@patch("services.folder_service.update_folder_size_hierarchy")
async def test_delete_file_updates_hierarchy(mock_update, mock_file_class):
    file_id = PydanticObjectId()
    folder_id = PydanticObjectId()

    mock_file_instance = AsyncMock()
    mock_file_instance.file_size = 2000
    mock_file_instance.folder_id = folder_id
    mock_file_class.get = AsyncMock(return_value=mock_file_instance)

    res = await delete_file(file_id)

    assert res is True
    mock_file_instance.delete.assert_called_once()
    mock_update.assert_called_once_with(folder_id, -2000)

@pytest.mark.asyncio
@patch("services.file_service.File")
@patch("services.folder_service.update_folder_size_hierarchy")
async def test_move_file_updates_hierarchy(mock_update, mock_file_class):
    file_id = PydanticObjectId()
    old_folder_id = PydanticObjectId()
    new_folder_id = PydanticObjectId()

    mock_file_instance = AsyncMock()
    mock_file_instance.file_size = 3000
    mock_file_instance.folder_id = old_folder_id
    mock_file_class.get = AsyncMock(return_value=mock_file_instance)
    mock_file_class.find_one = AsyncMock(return_value=None)

    await move_file(file_id, new_folder_id)

    mock_file_instance.save.assert_called_once()
    mock_update.assert_any_call(old_folder_id, -3000)
    mock_update.assert_any_call(new_folder_id, 3000)
