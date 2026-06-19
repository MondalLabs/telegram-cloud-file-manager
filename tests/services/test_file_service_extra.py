import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from beanie import PydanticObjectId
from services.file_service import (
    get_files_in_folder,
    count_files_in_folder,
    get_files_in_folder_paginated,
    get_file,
    rename_file,
    route_to_cdn,
    create_file,
    delete_file,
    move_file,
    copy_file
)

@pytest.mark.asyncio
@patch("services.file_service.File")
async def test_get_files_in_folder(mock_file_class):
    find_mock = MagicMock()
    find_mock.sort.return_value.to_list = AsyncMock(return_value=[])
    mock_file_class.find = MagicMock(return_value=find_mock)
    
    fid = PydanticObjectId()
    res = await get_files_in_folder(fid)
    assert res == []

@pytest.mark.asyncio
@patch("services.file_service.File")
async def test_count_files_in_folder(mock_file_class):
    find_mock = MagicMock()
    find_mock.count = AsyncMock(return_value=12)
    mock_file_class.find = MagicMock(return_value=find_mock)
    
    res = await count_files_in_folder(None)
    assert res == 12

@pytest.mark.asyncio
@patch("services.file_service.File")
async def test_get_files_in_folder_paginated(mock_file_class):
    find_mock = MagicMock()
    sort_mock = MagicMock()
    skip_mock = MagicMock()
    limit_mock = MagicMock()
    
    find_mock.sort.return_value = sort_mock
    sort_mock.skip.return_value = skip_mock
    skip_mock.limit.return_value = limit_mock
    limit_mock.to_list = AsyncMock(return_value=[])
    
    mock_file_class.find = MagicMock(return_value=find_mock)
    
    res = await get_files_in_folder_paginated(None, skip=10, limit=5)
    assert res == []

@pytest.mark.asyncio
@patch("services.file_service.File")
async def test_get_file(mock_file_class):
    fid = PydanticObjectId()
    mock_file_class.get = AsyncMock(return_value=None)
    res = await get_file(fid)
    assert res is None

@pytest.mark.asyncio
@patch("services.file_service.File")
async def test_rename_file_success(mock_file_class):
    fid = PydanticObjectId()
    mock_file = AsyncMock()
    mock_file.name = "old.txt"
    mock_file.save = AsyncMock()
    mock_file_class.get = AsyncMock(return_value=mock_file)
    
    res = await rename_file(fid, "new.txt")
    assert res == mock_file
    assert mock_file.name == "new.txt"
    mock_file.save.assert_called_once()

@pytest.mark.asyncio
@patch("services.file_service.File")
async def test_rename_file_not_found(mock_file_class):
    mock_file_class.get = AsyncMock(return_value=None)
    res = await rename_file(PydanticObjectId(), "new.txt")
    assert res is None

@pytest.mark.asyncio
@patch("services.file_service.BotSettings.get_dump_chat_id")
async def test_route_to_cdn_no_dump_chat_id(mock_get_dump):
    mock_get_dump.return_value = None
    client = MagicMock()
    message = MagicMock()
    
    with pytest.raises(RuntimeError, match="Dump group not configured."):
        await route_to_cdn(client, message, PydanticObjectId(), 123)

@pytest.mark.asyncio
@patch("services.file_service.BotSettings.get_dump_chat_id")
async def test_route_to_cdn_unsupported_media(mock_get_dump):
    mock_get_dump.return_value = -10012345
    client = MagicMock()
    message = MagicMock()
    message.photo = None
    message.video = None
    message.document = None
    
    with pytest.raises(ValueError, match="Message contains no supported media"):
        await route_to_cdn(client, message, PydanticObjectId(), 123)

@pytest.mark.asyncio
@patch("services.file_service.BotSettings.get_dump_chat_id")
@patch("services.file_service.create_file")
async def test_route_to_cdn_photo_success(mock_create_file, mock_get_dump):
    mock_get_dump.return_value = -10012345
    
    client = AsyncMock()
    copied_msg = AsyncMock()
    copied_msg.id = 55
    copied_photo = MagicMock()
    copied_photo.file_id = "photo_cdn_id"
    copied_msg.photo = copied_photo
    copied_msg.video = None
    copied_msg.document = None
    client.copy_message = AsyncMock(return_value=copied_msg)
    
    message = MagicMock()
    message.chat.id = 111
    message.id = 222
    photo_mock = MagicMock()
    photo_mock.file_name = "test.jpg"
    photo_mock.file_size = 1000
    photo_mock.mime_type = "image/jpeg"
    message.photo = photo_mock
    message.video = None
    message.document = None
    
    await route_to_cdn(client, message, PydanticObjectId(), 123)
    
    client.copy_message.assert_called_once_with(
        chat_id=-10012345,
        from_chat_id=111,
        message_id=222
    )
    mock_create_file.assert_called_once()

@pytest.mark.asyncio
@patch("services.file_service.BotSettings.get_dump_chat_id")
async def test_route_to_cdn_copy_failed(mock_get_dump):
    mock_get_dump.return_value = -10012345
    
    client = AsyncMock()
    copied_msg = AsyncMock()
    copied_msg.photo = None
    copied_msg.video = None
    copied_msg.document = None
    client.copy_message = AsyncMock(return_value=copied_msg)
    
    message = MagicMock()
    video_mock = MagicMock()
    message.video = video_mock
    message.photo = None
    message.document = None
    
    with pytest.raises(RuntimeError, match="CDN copy failed"):
        await route_to_cdn(client, message, PydanticObjectId(), 123)

@pytest.mark.asyncio
@patch("services.file_service.File")
@patch("services.folder_service.update_folder_size_hierarchy", new_callable=AsyncMock)
async def test_create_file_size_gt_zero(mock_update_size, mock_file_class):
    mock_file_instance = MagicMock()
    mock_file_instance.file_size = 500
    mock_file_instance.folder_id = PydanticObjectId()
    mock_file_instance.insert = AsyncMock()
    mock_file_class.return_value = mock_file_instance
    
    res = await create_file(
        name="test.mp4",
        file_id="abc",
        file_type="video",
        folder_id=mock_file_instance.folder_id,
        uploaded_by=123,
        file_size=500
    )
    assert res == mock_file_instance
    mock_file_instance.insert.assert_called_once()
    mock_update_size.assert_called_once_with(mock_file_instance.folder_id, 500)

@pytest.mark.asyncio
@patch("services.file_service.File")
@patch("services.folder_service.update_folder_size_hierarchy", new_callable=AsyncMock)
async def test_delete_file_not_found(mock_update_size, mock_file_class):
    mock_file_class.get = AsyncMock(return_value=None)
    res = await delete_file(PydanticObjectId())
    assert res is False
    mock_update_size.assert_not_called()

@pytest.mark.asyncio
@patch("services.file_service.File")
@patch("services.folder_service.update_folder_size_hierarchy", new_callable=AsyncMock)
async def test_delete_file_success(mock_update_size, mock_file_class):
    mock_file = MagicMock()
    mock_file.file_size = 300
    mock_file.folder_id = PydanticObjectId()
    mock_file.delete = AsyncMock()
    mock_file_class.get = AsyncMock(return_value=mock_file)
    
    res = await delete_file(PydanticObjectId())
    assert res is True
    mock_file.delete.assert_called_once()
    mock_update_size.assert_called_once_with(mock_file.folder_id, -300)

@pytest.mark.asyncio
@patch("services.file_service.File")
@patch("services.folder_service.update_folder_size_hierarchy", new_callable=AsyncMock)
async def test_move_file_not_found(mock_update_size, mock_file_class):
    mock_file_class.get = AsyncMock(return_value=None)
    res = await move_file(PydanticObjectId(), PydanticObjectId())
    assert res is None

@pytest.mark.asyncio
@patch("services.file_service.File")
@patch("services.folder_service.update_folder_size_hierarchy", new_callable=AsyncMock)
async def test_move_file_success_with_conflict(mock_update_size, mock_file_class):
    fid = PydanticObjectId()
    mock_file = MagicMock()
    mock_file.name = "test.txt"
    mock_file.file_size = 400
    mock_file.folder_id = PydanticObjectId()
    mock_file.save = AsyncMock()
    mock_file_class.get = AsyncMock(return_value=mock_file)
    
    conflict_file = MagicMock()
    mock_file_class.find_one = AsyncMock(side_effect=[conflict_file, None])
    
    target_folder = PydanticObjectId()
    res = await move_file(fid, target_folder)
    assert res == mock_file
    assert mock_file.name == "test_1.txt"
    assert mock_file.folder_id == target_folder
    mock_file.save.assert_called_once()
    
    mock_update_size.assert_any_call(mock_update_size.call_args_list[0][0][0], -400)
    mock_update_size.assert_any_call(target_folder, 400)

@pytest.mark.asyncio
@patch("services.file_service.File")
@patch("services.folder_service.update_folder_size_hierarchy", new_callable=AsyncMock)
async def test_copy_file_not_found(mock_update_size, mock_file_class):
    mock_file_class.get = AsyncMock(return_value=None)
    res = await copy_file(PydanticObjectId(), PydanticObjectId(), 123)
    assert res is None

@pytest.mark.asyncio
@patch("services.file_service.File")
@patch("services.folder_service.update_folder_size_hierarchy", new_callable=AsyncMock)
async def test_copy_file_success_with_conflict(mock_update_size, mock_file_class):
    fid = PydanticObjectId()
    mock_file = MagicMock()
    mock_file.name = "test.txt"
    mock_file.file_id = "cdn_id"
    mock_file.file_type = "document"
    mock_file.dump_message_id = 99
    mock_file.file_size = 600
    mock_file.duration = None
    mock_file.width = None
    mock_file.height = None
    mock_file.mime_type = "text/plain"
    mock_file_class.get = AsyncMock(return_value=mock_file)
    
    conflict_file = MagicMock()
    mock_file_class.find_one = AsyncMock(side_effect=[conflict_file, None])
    
    new_file_mock = MagicMock()
    new_file_mock.file_size = 600
    new_file_mock.folder_id = PydanticObjectId()
    new_file_mock.insert = AsyncMock()
    mock_file_class.return_value = new_file_mock
    
    target_folder = PydanticObjectId()
    res = await copy_file(fid, target_folder, 123)
    assert res == new_file_mock
    new_file_mock.insert.assert_called_once()
    mock_update_size.assert_called_once_with(new_file_mock.folder_id, 600)

@pytest.mark.asyncio
@patch("services.file_service.BotSettings.get_dump_chat_id")
@patch("services.file_service.create_file")
async def test_route_to_cdn_document_success(mock_create_file, mock_get_dump):
    mock_get_dump.return_value = -10012345
    
    client = AsyncMock()
    copied_msg = AsyncMock()
    copied_msg.id = 55
    copied_doc = MagicMock()
    copied_doc.file_id = "doc_cdn_id"
    copied_msg.document = copied_doc
    copied_msg.photo = None
    copied_msg.video = None
    client.copy_message = AsyncMock(return_value=copied_msg)
    
    message = MagicMock()
    message.chat.id = 111
    message.id = 222
    doc_mock = MagicMock()
    doc_mock.file_name = "test.pdf"
    doc_mock.file_size = 2000
    doc_mock.mime_type = "application/pdf"
    message.document = doc_mock
    message.photo = None
    message.video = None
    
    await route_to_cdn(client, message, PydanticObjectId(), 123)
    client.copy_message.assert_called_once()
    mock_create_file.assert_called_once()

@pytest.mark.asyncio
@patch("services.file_service.BotSettings.get_dump_chat_id")
@patch("services.file_service.create_file")
async def test_route_to_cdn_long_name(mock_create_file, mock_get_dump):
    mock_get_dump.return_value = -10012345
    
    client = AsyncMock()
    copied_msg = AsyncMock()
    copied_doc = MagicMock()
    copied_doc.file_id = "doc_cdn_id"
    copied_msg.document = copied_doc
    copied_msg.photo = None
    copied_msg.video = None
    client.copy_message = AsyncMock(return_value=copied_msg)
    
    message = MagicMock()
    doc_mock = MagicMock()
    doc_mock.file_name = "a" * 150 + ".pdf"
    doc_mock.file_size = 2000
    doc_mock.mime_type = "application/pdf"
    message.document = doc_mock
    message.photo = None
    message.video = None
    
    await route_to_cdn(client, message, PydanticObjectId(), 123)
    args, kwargs = mock_create_file.call_args
    assert len(kwargs["name"]) <= 128

@pytest.mark.asyncio
@patch("services.file_service.File")
@patch("services.folder_service.update_folder_size_hierarchy", new_callable=AsyncMock)
async def test_move_file_no_dot_and_invalid_size(mock_update_size, mock_file_class):
    fid = PydanticObjectId()
    mock_file = MagicMock()
    mock_file.name = "filename_no_extension"
    mock_file.file_size = "not-an-int"
    mock_file.folder_id = PydanticObjectId()
    mock_file.save = AsyncMock()
    mock_file_class.get = AsyncMock(return_value=mock_file)
    
    conflict_file = MagicMock()
    mock_file_class.find_one = AsyncMock(side_effect=[conflict_file, None])
    
    target_folder = PydanticObjectId()
    res = await move_file(fid, target_folder)
    assert res == mock_file
    assert mock_file.name == "filename_no_extension_1"
    mock_update_size.assert_not_called()

@pytest.mark.asyncio
@patch("services.file_service.File")
@patch("services.folder_service.update_folder_size_hierarchy", new_callable=AsyncMock)
async def test_create_file_zero_or_invalid_size(mock_update_size, mock_file_class):
    # Test zero size
    f1 = MagicMock()
    f1.file_size = 0
    f1.folder_id = PydanticObjectId()
    f1.insert = AsyncMock()
    mock_file_class.return_value = f1
    
    res1 = await create_file(
        name="test1.txt",
        file_id="id1",
        file_type="document",
        folder_id=f1.folder_id,
        uploaded_by=123,
        file_size=0
    )
    assert res1 == f1
    mock_update_size.assert_not_called()
    
    # Test invalid size type (e.g. string)
    f2 = MagicMock()
    f2.file_size = "invalid"
    f2.folder_id = PydanticObjectId()
    f2.insert = AsyncMock()
    mock_file_class.return_value = f2
    
    res2 = await create_file(
        name="test2.txt",
        file_id="id2",
        file_type="document",
        folder_id=f2.folder_id,
        uploaded_by=123,
        file_size="invalid"
    )
    assert res2 == f2
    mock_update_size.assert_not_called()

@pytest.mark.asyncio
@patch("services.file_service.File")
@patch("services.folder_service.update_folder_size_hierarchy", new_callable=AsyncMock)
async def test_delete_file_zero_or_invalid_size(mock_update_size, mock_file_class):
    # Test zero size delete
    fid1 = PydanticObjectId()
    f1 = MagicMock()
    f1.file_size = 0
    f1.folder_id = PydanticObjectId()
    f1.delete = AsyncMock()
    mock_file_class.get = AsyncMock(return_value=f1)
    
    res1 = await delete_file(fid1)
    assert res1 is True
    f1.delete.assert_called_once()
    mock_update_size.assert_not_called()
    
    # Test invalid size delete
    fid2 = PydanticObjectId()
    f2 = MagicMock()
    f2.file_size = "invalid"
    f2.folder_id = PydanticObjectId()
    f2.delete = AsyncMock()
    mock_file_class.get = AsyncMock(return_value=f2)
    
    res2 = await delete_file(fid2)
    assert res2 is True
    f2.delete.assert_called_once()
    mock_update_size.assert_not_called()

@pytest.mark.asyncio
@patch("services.file_service.File")
@patch("services.folder_service.update_folder_size_hierarchy", new_callable=AsyncMock)
async def test_copy_file_no_dot_and_invalid_size(mock_update_size, mock_file_class):
    fid = PydanticObjectId()
    mock_file = MagicMock()
    mock_file.name = "filename_no_extension"
    mock_file.file_id = "cdn_id"
    mock_file.file_type = "document"
    mock_file.dump_message_id = 99
    mock_file.file_size = "not-an-int"
    mock_file.duration = None
    mock_file.width = None
    mock_file.height = None
    mock_file.mime_type = "text/plain"
    mock_file_class.get = AsyncMock(return_value=mock_file)
    
    conflict_file = MagicMock()
    mock_file_class.find_one = AsyncMock(side_effect=[conflict_file, None])
    
    new_file_mock = MagicMock()
    new_file_mock.file_size = "not-an-int"
    new_file_mock.folder_id = PydanticObjectId()
    new_file_mock.insert = AsyncMock()
    mock_file_class.return_value = new_file_mock
    
    target_folder = PydanticObjectId()
    res = await copy_file(fid, target_folder, 123)
    assert res == new_file_mock
    mock_update_size.assert_not_called()

@pytest.mark.asyncio
@patch("services.file_service.BotSettings.get_dump_chat_id")
@patch("services.file_service.create_file")
async def test_route_to_cdn_too_long_no_dot_or_long_ext(mock_create_file, mock_get_dump):
    mock_get_dump.return_value = -10012345
    
    client = AsyncMock()
    copied_msg = AsyncMock()
    copied_doc = MagicMock()
    copied_doc.file_id = "doc_cdn_id"
    copied_msg.document = copied_doc
    copied_msg.photo = None
    copied_msg.video = None
    client.copy_message = AsyncMock(return_value=copied_msg)
    
    # 1. No dot
    message1 = MagicMock()
    doc_mock1 = MagicMock()
    doc_mock1.file_name = "a" * 150
    doc_mock1.file_size = 2000
    doc_mock1.mime_type = "application/pdf"
    message1.document = doc_mock1
    message1.photo = None
    message1.video = None
    
    await route_to_cdn(client, message1, PydanticObjectId(), 123)
    args, kwargs = mock_create_file.call_args
    assert len(kwargs["name"]) == 128
    assert "." not in kwargs["name"]
    
    # 2. Long extension (>= 10 chars)
    message2 = MagicMock()
    doc_mock2 = MagicMock()
    doc_mock2.file_name = "a" * 150 + ".verylongextension"
    doc_mock2.file_size = 2000
    doc_mock2.mime_type = "application/pdf"
    message2.document = doc_mock2
    message2.photo = None
    message2.video = None
    
    await route_to_cdn(client, message2, PydanticObjectId(), 123)
    args, kwargs = mock_create_file.call_args
    assert len(kwargs["name"]) == 128
