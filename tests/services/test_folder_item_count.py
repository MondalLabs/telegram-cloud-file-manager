import pytest
from unittest.mock import AsyncMock, patch
from beanie import PydanticObjectId
from services.folder_service import get_immediate_item_counts

@pytest.mark.asyncio
@patch("services.folder_service.Folder")
@patch("services.folder_service.File")
async def test_get_immediate_item_counts(mock_file_class, mock_folder_class):
    # Setup parent folder IDs
    fid1 = PydanticObjectId()
    fid2 = PydanticObjectId()
    
    # Mock Folder.aggregate().to_list() for subfolder counts
    mock_folder_agg = AsyncMock()
    mock_folder_agg.to_list.return_value = [
        {"_id": fid1, "count": 2},
        {"_id": fid2, "count": 1}
    ]
    mock_folder_class.aggregate.return_value = mock_folder_agg
    
    # Mock File.aggregate().to_list() for file counts
    mock_file_agg = AsyncMock()
    mock_file_agg.to_list.return_value = [
        {"_id": fid1, "count": 3}
    ]
    mock_file_class.aggregate.return_value = mock_file_agg
    
    # Execute count retrieval
    counts = await get_immediate_item_counts([fid1, fid2])
    
    # Verify proper aggregation summing folders and files
    assert counts[fid1] == 5  # 2 folders + 3 files
    assert counts[fid2] == 1  # 1 folder + 0 files
    
    # Assert query pipelines were executed
    mock_folder_class.aggregate.assert_called_once()
    mock_file_class.aggregate.assert_called_once()

@pytest.mark.asyncio
async def test_get_immediate_item_counts_empty():
    # Verify empty folder lists return immediately with no DB calls
    counts = await get_immediate_item_counts([])
    assert counts == {}
