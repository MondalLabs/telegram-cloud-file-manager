import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from beanie import PydanticObjectId
from beanie.odm.fields import ExpressionField

from services.folder_service import rename_folder
from models.folder import Folder

@pytest.fixture
def mock_folder_id():
    return PydanticObjectId("65b1c5f3e4b0000000000001")

@pytest.fixture
def mock_parent_id():
    return PydanticObjectId("65b1c5f3e4b0000000000002")

@pytest.fixture
def mock_folder(mock_folder_id, mock_parent_id):
    folder = MagicMock(spec=Folder)
    folder.id = mock_folder_id
    folder.parent_id = mock_parent_id
    folder.name = "old_name"
    folder.save = AsyncMock()
    return folder

@pytest.mark.asyncio
async def test_rename_folder_not_found(mock_folder_id):
    """Test renaming a folder that does not exist returns None."""
    with patch("services.folder_service.Folder.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None

        result = await rename_folder(mock_folder_id, "new_name")

        mock_get.assert_called_once_with(mock_folder_id)
        assert result is None

@pytest.mark.asyncio
async def test_rename_folder_success(mock_folder_id, mock_folder):
    """Test successful rename when no duplicate sibling exists."""
    with patch("services.folder_service.Folder.get", new_callable=AsyncMock) as mock_get, \
         patch("services.folder_service.Folder.find_one", new_callable=AsyncMock) as mock_find_one, \
         patch("services.folder_service.Folder.name", new=ExpressionField("name"), create=True), \
         patch("services.folder_service.Folder.parent_id", new=ExpressionField("parent_id"), create=True), \
         patch("services.folder_service.Folder.id", new=ExpressionField("_id"), create=True):

        mock_get.return_value = mock_folder
        mock_find_one.return_value = None  # No duplicate sibling

        new_name = "new_name"
        result = await rename_folder(mock_folder_id, new_name)

        mock_get.assert_called_once_with(mock_folder_id)
        mock_find_one.assert_called_once()

        # Verify folder name was updated and save was called
        assert mock_folder.name == new_name
        mock_folder.save.assert_called_once()

        assert result == mock_folder

@pytest.mark.asyncio
async def test_rename_folder_duplicate_sibling(mock_folder_id, mock_folder):
    """Test renaming a folder to a name that already exists in the same parent raises ValueError."""
    with patch("services.folder_service.Folder.get", new_callable=AsyncMock) as mock_get, \
         patch("services.folder_service.Folder.find_one", new_callable=AsyncMock) as mock_find_one, \
         patch("services.folder_service.Folder.name", new=ExpressionField("name"), create=True), \
         patch("services.folder_service.Folder.parent_id", new=ExpressionField("parent_id"), create=True), \
         patch("services.folder_service.Folder.id", new=ExpressionField("_id"), create=True):

        mock_get.return_value = mock_folder

        # Simulate an existing sibling
        mock_sibling = MagicMock(spec=Folder)
        mock_find_one.return_value = mock_sibling

        new_name = "duplicate_name"

        with pytest.raises(ValueError, match=f"A folder named '{new_name}' already exists here."):
            await rename_folder(mock_folder_id, new_name)

        mock_get.assert_called_once_with(mock_folder_id)
        mock_find_one.assert_called_once()

        # Verify save was NOT called
        mock_folder.save.assert_not_called()
