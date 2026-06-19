import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from beanie import PydanticObjectId
from bson import ObjectId
from services.folder_service import (
    get_children,
    count_children,
    get_children_paginated,
    get_folder,
    rename_folder,
    get_breadcrumbs,
    move_folder,
    get_folder_size,
    recalculate_all_folder_sizes,
    delete_folder_tree,
    copy_folder,
    update_folder_size_hierarchy
)

@pytest.mark.asyncio
@patch("services.folder_service.Folder")
async def test_get_children(mock_folder_class):
    find_mock = MagicMock()
    find_mock.sort.return_value.to_list = AsyncMock(return_value=[])
    mock_folder_class.find = MagicMock(return_value=find_mock)
    
    res = await get_children(None)
    assert res == []

@pytest.mark.asyncio
@patch("services.folder_service.Folder")
async def test_count_children(mock_folder_class):
    find_mock = MagicMock()
    find_mock.count = AsyncMock(return_value=4)
    mock_folder_class.find = MagicMock(return_value=find_mock)
    
    res = await count_children(None)
    assert res == 4

@pytest.mark.asyncio
@patch("services.folder_service.Folder")
async def test_get_children_paginated(mock_folder_class):
    find_mock = MagicMock()
    sort_mock = MagicMock()
    skip_mock = MagicMock()
    limit_mock = MagicMock()
    
    find_mock.sort.return_value = sort_mock
    sort_mock.skip.return_value = skip_mock
    skip_mock.limit.return_value = limit_mock
    limit_mock.to_list = AsyncMock(return_value=[])
    
    mock_folder_class.find = MagicMock(return_value=find_mock)
    
    res = await get_children_paginated(None, skip=10, limit=5)
    assert res == []

@pytest.mark.asyncio
@patch("services.folder_service.Folder")
async def test_get_folder(mock_folder_class):
    fid = PydanticObjectId()
    mock_folder_class.get = AsyncMock(return_value=None)
    res = await get_folder(fid)
    assert res is None

@pytest.mark.asyncio
@patch("services.folder_service.Folder")
async def test_rename_folder_success(mock_folder_class):
    fid = PydanticObjectId()
    folder = AsyncMock()
    folder.name = "old"
    folder.parent_id = None
    folder.save = AsyncMock()
    
    mock_folder_class.get = AsyncMock(return_value=folder)
    mock_folder_class.find_one = AsyncMock(return_value=None)
    
    res = await rename_folder(fid, "new")
    assert res == folder
    assert folder.name == "new"
    folder.save.assert_called_once()

@pytest.mark.asyncio
@patch("services.folder_service.Folder")
async def test_rename_folder_conflict(mock_folder_class):
    fid = PydanticObjectId()
    folder = AsyncMock()
    folder.name = "old"
    folder.parent_id = None
    mock_folder_class.get = AsyncMock(return_value=folder)
    mock_folder_class.find_one = AsyncMock(return_value=MagicMock())
    
    with pytest.raises(ValueError, match="already exists here"):
        await rename_folder(fid, "conflict")

@pytest.mark.asyncio
@patch("services.folder_service.Folder")
async def test_rename_folder_not_found(mock_folder_class):
    mock_folder_class.get = AsyncMock(return_value=None)
    res = await rename_folder(PydanticObjectId(), "name")
    assert res is None

@pytest.mark.asyncio
@patch("services.folder_service.Folder")
async def test_get_breadcrumbs(mock_folder_class):
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
    
    crumbs = await get_breadcrumbs(child_id)
    assert len(crumbs) == 2
    assert crumbs[0] == parent_folder
    assert crumbs[1] == child_folder

@pytest.mark.asyncio
@patch("services.folder_service.Folder")
async def test_move_folder_not_found(mock_folder_class):
    mock_folder_class.get = AsyncMock(return_value=None)
    with pytest.raises(ValueError, match="Folder not found."):
        await move_folder(PydanticObjectId(), None)

@pytest.mark.asyncio
@patch("services.folder_service.Folder")
@patch("services.folder_service.File")
async def test_get_folder_size(mock_file_class, mock_folder_class):
    # Mock aggregates
    mock_folder_class.aggregate = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[{"descendant_ids": [ObjectId()]}])))
    mock_file_class.aggregate = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[{"total_size": 5000, "total_files": 3}])))
    
    stats = await get_folder_size(PydanticObjectId())
    assert stats["size"] == 5000
    assert stats["files_count"] == 3
    assert stats["folders_count"] == 1

@pytest.mark.asyncio
@patch("services.folder_service.Folder")
@patch("services.folder_service.File")
async def test_recalculate_all_folder_sizes(mock_file_class, mock_folder_class):
    fid = PydanticObjectId()
    folder = MagicMock()
    folder.id = fid
    folder.parent_id = None
    
    mock_find = MagicMock()
    mock_find.to_list = AsyncMock(return_value=[folder])
    mock_folder_class.find_all = MagicMock(return_value=mock_find)
    
    mock_file_class.aggregate = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[{"_id": fid, "total_size": 9000}])))
    
    mock_collection = MagicMock()
    mock_collection.update_one = AsyncMock()
    mock_folder_class.get_pymongo_collection.return_value = mock_collection
    
    await recalculate_all_folder_sizes()
    mock_collection.update_one.assert_called_once_with({"_id": fid}, {"$set": {"size": 9000}})

@pytest.mark.asyncio
@patch("services.folder_service.Folder")
@patch("services.folder_service.File")
@patch("services.folder_service.update_folder_size_hierarchy", new_callable=AsyncMock)
async def test_delete_folder_tree(mock_update_size, mock_file_class, mock_folder_class):
    target_id = PydanticObjectId()
    mock_folder_class.aggregate.return_value.to_list = AsyncMock(return_value=[{"descendant_ids": [ObjectId()]}])
    
    mock_folder = MagicMock()
    mock_folder.parent_id = PydanticObjectId()
    mock_folder.size = 1500
    mock_folder_class.get = AsyncMock(return_value=mock_folder)
    
    mock_file_class.find.return_value.delete = AsyncMock(return_value=MagicMock(deleted_count=3))
    mock_folder_class.find.return_value.delete = AsyncMock(return_value=MagicMock(deleted_count=2))
    
    res = await delete_folder_tree(target_id)
    assert res["folders_deleted"] == 2
    assert res["files_deleted"] == 3
    mock_update_size.assert_called_once_with(mock_folder.parent_id, -1500)

@pytest.mark.asyncio
@patch("services.folder_service.Folder")
@patch("services.folder_service.File")
@patch("services.folder_service.update_folder_size_hierarchy", new_callable=AsyncMock)
async def test_copy_folder(mock_update_size, mock_file_class, mock_folder_class):
    src_id = PydanticObjectId()
    target_parent = PydanticObjectId()
    
    src_folder = MagicMock()
    src_folder.name = "Movies"
    
    child_fld = MagicMock()
    child_fld.id = PydanticObjectId()
    child_file = MagicMock()
    child_file.name = "clip.mp4"
    child_file.file_size = 500
    
    async def mock_get(fid):
        if fid == src_id:
            return src_folder
        return MagicMock()
        
    mock_folder_class.get = AsyncMock(side_effect=mock_get)
    mock_folder_class.find_one = AsyncMock(return_value=None)
    mock_folder_class.find.return_value.to_list = AsyncMock(side_effect=[[child_fld], []])
    mock_file_class.find.return_value.to_list = AsyncMock(return_value=[child_file])
    mock_file_class.return_value.insert = AsyncMock()
    
    new_fld_mock = MagicMock()
    new_fld_mock.insert = AsyncMock()
    mock_folder_class.return_value = new_fld_mock
    
    res = await copy_folder(src_id, target_parent, 123)
    assert res is not None

@pytest.mark.asyncio
@patch("services.folder_service.Folder")
async def test_update_folder_size_hierarchy(mock_folder_class):
    await update_folder_size_hierarchy(PydanticObjectId(), 0)
    mock_folder_class.get.assert_not_called()
    
    parent_id = PydanticObjectId()
    child_id = PydanticObjectId()
    
    child = MagicMock()
    child.id = child_id
    child.parent_id = parent_id
    
    parent = MagicMock()
    parent.id = parent_id
    parent.parent_id = None
    
    async def mock_get(fid):
        if fid == child_id:
            return child
        if fid == parent_id:
            return parent
        return None
        
    mock_folder_class.get = AsyncMock(side_effect=mock_get)
    
    mock_collection = MagicMock()
    mock_collection.update_one = AsyncMock()
    mock_folder_class.get_pymongo_collection.return_value = mock_collection
    
    await update_folder_size_hierarchy(child_id, 100)
    assert mock_collection.update_one.call_count == 2

@pytest.mark.asyncio
@patch("services.folder_service.Folder")
@patch("services.folder_service.File")
@patch("services.folder_service.update_folder_size_hierarchy", new_callable=AsyncMock)
async def test_delete_folder_tree_root_no_size(mock_update_size, mock_file_class, mock_folder_class):
    target_id = PydanticObjectId()
    mock_folder_class.aggregate.return_value.to_list = AsyncMock(return_value=[])
    
    mock_folder = MagicMock()
    mock_folder.parent_id = None
    mock_folder.size = 0
    mock_folder_class.get = AsyncMock(return_value=mock_folder)
    
    mock_file_class.find.return_value.delete = AsyncMock(return_value=MagicMock(deleted_count=0))
    mock_folder_class.find.return_value.delete = AsyncMock(return_value=MagicMock(deleted_count=1))
    
    res = await delete_folder_tree(target_id)
    assert res["folders_deleted"] == 1
    mock_update_size.assert_not_called()

@pytest.mark.asyncio
@patch("services.folder_service.Folder")
async def test_get_breadcrumbs_not_found(mock_folder_class):
    mock_folder_class.get = AsyncMock(return_value=None)
    crumbs = await get_breadcrumbs(PydanticObjectId())
    assert crumbs == []

@pytest.mark.asyncio
@patch("services.folder_service.Folder")
@patch("services.folder_service.update_folder_size_hierarchy", new_callable=AsyncMock)
async def test_move_folder_conflict_and_invalid_size(mock_update_size, mock_folder_class):
    fid = PydanticObjectId()
    folder = MagicMock()
    folder.name = "old"
    folder.parent_id = None
    folder.size = "invalid-size"
    folder.save = AsyncMock()
    mock_folder_class.get = AsyncMock(return_value=folder)
    
    conflict_fld = MagicMock()
    mock_folder_class.find_one = AsyncMock(side_effect=[conflict_fld, None])
    
    target_parent = PydanticObjectId()
    res = await move_folder(fid, target_parent)
    assert res == folder
    assert folder.name == "old_1"
    mock_update_size.assert_not_called()

@pytest.mark.asyncio
@patch("services.folder_service.Folder")
@patch("services.folder_service.File")
async def test_copy_folder_not_found_and_conflict(mock_file_class, mock_folder_class):
    mock_folder_class.get = AsyncMock(return_value=None)
    with pytest.raises(ValueError, match="Source folder not found."):
        await copy_folder(PydanticObjectId(), None, 123)
        
    src_folder = MagicMock()
    src_folder.name = "Movies"
    mock_folder_class.get = AsyncMock(return_value=src_folder)
    
    conflict_fld = MagicMock()
    mock_folder_class.find_one = AsyncMock(side_effect=[conflict_fld, None])
    mock_folder_class.find.return_value.to_list = AsyncMock(return_value=[])
    mock_file_class.find.return_value.to_list = AsyncMock(return_value=[])
    
    new_fld = MagicMock()
    new_fld.insert = AsyncMock()
    mock_folder_class.return_value = new_fld
    
    res = await copy_folder(PydanticObjectId(), None, 123)
    assert res is not None

@pytest.mark.asyncio
@patch("services.folder_service.Folder")
async def test_update_folder_size_hierarchy_not_found(mock_folder_class):
    mock_folder_class.get = AsyncMock(return_value=None)
    await update_folder_size_hierarchy(PydanticObjectId(), 100)

@pytest.mark.asyncio
@patch("services.folder_service.Folder")
@patch("services.folder_service.File")
@patch("services.folder_service.update_folder_size_hierarchy", new_callable=AsyncMock)
async def test_delete_folder_tree_invalid_size_and_no_parent(mock_update_size, mock_file_class, mock_folder_class):
    # 1. No parent_id
    folder_no_parent = MagicMock()
    folder_no_parent.parent_id = None
    folder_no_parent.size = 100
    mock_folder_class.get = AsyncMock(return_value=folder_no_parent)
    
    mock_folder_class.aggregate.return_value.to_list = AsyncMock(return_value=[{"descendant_ids": []}])
    
    # Mock delete calls
    del_mock = MagicMock()
    del_mock.deleted_count = 1
    mock_file_class.find.return_value.delete = AsyncMock(return_value=del_mock)
    mock_folder_class.find.return_value.delete = AsyncMock(return_value=del_mock)
    
    res = await delete_folder_tree(PydanticObjectId())
    assert res["folders_deleted"] == 1
    mock_update_size.assert_not_called()
    
    # 2. Parent exists, but size is not an int or is <= 0
    folder_zero_size = MagicMock()
    folder_zero_size.parent_id = PydanticObjectId()
    folder_zero_size.size = 0
    mock_folder_class.get = AsyncMock(return_value=folder_zero_size)
    
    await delete_folder_tree(PydanticObjectId())
    mock_update_size.assert_not_called()
    
    # size is invalid string
    folder_invalid_size = MagicMock()
    folder_invalid_size.parent_id = PydanticObjectId()
    folder_invalid_size.size = "invalid"
    mock_folder_class.get = AsyncMock(return_value=folder_invalid_size)
    
    await delete_folder_tree(PydanticObjectId())
    mock_update_size.assert_not_called()

@pytest.mark.asyncio
@patch("services.folder_service.Folder")
async def test_move_folder_nonexistent_parent(mock_folder_class):
    fid = PydanticObjectId()
    folder = MagicMock()
    folder.name = "sub"
    folder.parent_id = None
    folder.size = 100
    folder.save = AsyncMock()
    
    target_parent = PydanticObjectId()
    
    # 1. Folder.get(folder_id) -> folder
    # 2. Inside the self-nesting check, Folder.get(target_parent) -> None
    # 3. Inside update_folder_size_hierarchy for target_parent, Folder.get(target_parent) -> None
    def get_side_effect(oid):
        if oid == fid:
            return folder
        return None
    mock_folder_class.get = AsyncMock(side_effect=get_side_effect)
    mock_folder_class.find_one = AsyncMock(return_value=None)
    
    res = await move_folder(fid, target_parent)
    assert res == folder
    assert folder.parent_id == target_parent

@pytest.mark.asyncio
@patch("services.folder_service.Folder")
@patch("services.folder_service.update_folder_size_hierarchy", new_callable=AsyncMock)
async def test_move_folder_size_hierarchy_updated(mock_update_size, mock_folder_class):
    fid = PydanticObjectId()
    folder = MagicMock()
    folder.name = "sub"
    folder.parent_id = PydanticObjectId()
    folder.size = 500
    folder.save = AsyncMock()
    
    target_parent = PydanticObjectId()
    
    # Mocking:
    # 1. Folder.get(folder_id) -> folder
    # 2. Inside the self-nesting check, Folder.get(target_parent) -> target_parent_folder (parent_id = None)
    target_parent_folder = MagicMock()
    target_parent_folder.parent_id = None
    
    def get_side_effect(oid):
        if oid == fid:
            return folder
        if oid == target_parent:
            return target_parent_folder
        return None
    mock_folder_class.get = AsyncMock(side_effect=get_side_effect)
    mock_folder_class.find_one = AsyncMock(return_value=None)
    
    old_parent_id = folder.parent_id
    res = await move_folder(fid, target_parent)
    assert res == folder
    # Should call update_folder_size_hierarchy on old_parent_id with -500 and target_parent_id with 500
    mock_update_size.assert_any_call(old_parent_id, -500)
    mock_update_size.assert_any_call(target_parent, 500)

@pytest.mark.asyncio
@patch("services.folder_service.Folder")
@patch("services.folder_service.File")
@patch("services.folder_service.update_folder_size_hierarchy", new_callable=AsyncMock)
async def test_copy_folder_falsy_file_size(mock_update_size, mock_file_class, mock_folder_class):
    src_folder = MagicMock()
    src_folder.name = "Movies"
    mock_folder_class.get = AsyncMock(return_value=src_folder)
    
    mock_folder_class.find_one = AsyncMock(return_value=None)
    
    # No subfolders
    mock_folder_class.find.return_value.to_list = AsyncMock(return_value=[])
    
    # 1 file with size=0 or None
    f_mock = MagicMock()
    f_mock.name = "file.txt"
    f_mock.file_size = 0
    mock_file_class.find.return_value.to_list = AsyncMock(return_value=[f_mock])
    
    new_fld = MagicMock()
    new_fld.insert = AsyncMock()
    mock_folder_class.return_value = new_fld
    
    new_file_mock = MagicMock()
    new_file_mock.insert = AsyncMock()
    new_file_mock.file_size = 0
    mock_file_class.return_value = new_file_mock
    
    res = await copy_folder(PydanticObjectId(), None, 123)
    assert res is not None
    mock_update_size.assert_not_called()

@pytest.mark.asyncio
@patch("services.folder_service.Folder")
@patch("services.folder_service.File")
async def test_recalculate_all_folder_sizes_missing_folder_or_zero_size(mock_file_class, mock_folder_class):
    # Setup folders
    f1 = MagicMock()
    f1.id = PydanticObjectId()
    f1.parent_id = None
    
    f2 = MagicMock()
    f2.id = PydanticObjectId()
    f2.parent_id = PydanticObjectId() # points to a missing parent
    
    mock_folder_class.find_all.return_value.to_list = AsyncMock(return_value=[f1, f2])
    
    # Setup files:
    # 1. File pointing to f1 with size 300
    # 2. File pointing to a missing folder with size 400
    # 3. File pointing to f2 with size 0
    file_aggregate_res = [
        {"_id": f1.id, "total_size": 300},
        {"_id": PydanticObjectId(), "total_size": 400},
        {"_id": f2.id, "total_size": 0}
    ]
    mock_file_class.aggregate.return_value.to_list = AsyncMock(return_value=file_aggregate_res)
    
    mock_motor = MagicMock()
    mock_motor.update_one = AsyncMock()
    mock_folder_class.get_pymongo_collection = MagicMock(return_value=mock_motor)
    
    await recalculate_all_folder_sizes()
    # Verify updates are made
    mock_motor.update_one.assert_called()
