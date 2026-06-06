import pytest
from unittest.mock import AsyncMock, MagicMock
from beanie import PydanticObjectId
from services.folder_service import create_folder

@pytest.mark.asyncio
async def test_create_folder_duplicate_name(mocker):
    # Mock the Folder class in the services module to prevent Beanie Document attribute access issues
    mock_folder_class = mocker.patch("services.folder_service.Folder")
    mock_folder_class.find_one = AsyncMock(return_value=True) # Return truthy value to simulate existing folder

    # Mock class attributes to avoid AttributeError from Beanie/Pydantic
    mock_folder_class.name = MagicMock()
    mock_folder_class.parent_id = MagicMock()

    with pytest.raises(ValueError, match="A folder named 'duplicate_folder' already exists here."):
        await create_folder(
            name="duplicate_folder",
            parent_id=None,
            created_by=123,
        )
    mock_folder_class.find_one.assert_called_once()

@pytest.mark.asyncio
async def test_create_folder_success(mocker):
    # Create a mock for the returned Folder instance
    mock_folder_instance = AsyncMock()
    mock_folder_instance.name = "new_folder"
    mock_folder_instance.parent_id = None
    mock_folder_instance.created_by = 123

    # Mock the Folder class itself
    mock_folder_class = mocker.patch("services.folder_service.Folder", return_value=mock_folder_instance)
    mock_folder_class.find_one = AsyncMock(return_value=None)

    # Mock class attributes to avoid AttributeError from Beanie/Pydantic
    mock_folder_class.name = MagicMock()
    mock_folder_class.parent_id = MagicMock()

    folder = await create_folder(
        name="new_folder",
        parent_id=None,
        created_by=123,
    )

    assert folder.name == "new_folder"
    assert folder.parent_id is None
    assert folder.created_by == 123
    mock_folder_instance.insert.assert_called_once()
