import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from beanie import PydanticObjectId
from models.file import File
from models.user import User, UserRole
from models.folder import Folder
from models.state import FSMState
from models.settings import BotSettings

# Mock Beanie collection checks to allow DB-free instantiation
File._document_settings = MagicMock()
File.get_pymongo_collection = MagicMock()

User._document_settings = MagicMock()
User.get_pymongo_collection = MagicMock()

Folder._document_settings = MagicMock()
Folder.get_pymongo_collection = MagicMock()

FSMState._document_settings = MagicMock()
FSMState.get_pymongo_collection = MagicMock()

BotSettings._document_settings = MagicMock()
BotSettings.get_pymongo_collection = MagicMock()
BotSettings.key = MagicMock()

def test_file_repr_and_properties():
    f = File(
        name="test.mp4",
        file_id="abc",
        file_type="video",
        uploaded_by=123
    )
    f.id = PydanticObjectId()
    assert repr(f) == f"<File id={f.id} name='test.mp4' folder=None>"
    
    f.mime_type = "video/mp4"
    assert f.icon == "🎬"
    
    f.mime_type = "image/png"
    assert f.icon == "🖼️"
    
    f.mime_type = "application/pdf"
    assert f.icon == "📄"
    
    f.mime_type = "audio/mpeg"
    assert f.icon == "🎵"
    
    f.mime_type = "text/plain"
    assert f.icon == "📝"
    
    f.mime_type = "unknown/mime"
    f.file_type = "video"
    assert f.icon == "🎬"
    
    f.file_type = "document"
    assert f.icon == "📎"

    f.duration = 65
    f.width = 1920
    f.height = 1080
    f.file_size = 1024 * 1024 * 1024 + 1024 * 1024 * 50
    assert f.display_meta == "1m05s · 1920×1080 · 1.05 GB"
    
    f.duration = 45
    f.file_size = 1024 * 1024 * 5
    assert f.display_meta == "45s · 1920×1080 · 5.0 MB"
    
    f.duration = None
    f.width = None
    f.height = None
    f.file_size = None
    assert f.display_meta == "media"

def test_user_repr_and_display_name():
    u = User(telegram_id=123, role=UserRole.APPROVED)
    u.id = PydanticObjectId()
    assert repr(u) == f"<User id=123 role={UserRole.APPROVED}>"
    
    u.full_name = "John Doe"
    assert u.display_name == "John Doe"
    
    u.full_name = None
    u.username = "johndoe"
    assert u.display_name == "@johndoe"
    
    u.username = None
    assert u.display_name == "123"

def test_folder_repr():
    f = Folder(name="Movies", created_by=123)
    f.id = PydanticObjectId()
    assert repr(f) == f"<Folder id={f.id} name='Movies' parent=None>"

def test_fsm_state_repr():
    s = FSMState(telegram_id=123, state="waiting")
    assert repr(s) == "<FSMState user=123 state='waiting'>"

@pytest.mark.asyncio
@patch("models.settings.BotSettings.find_one", new_callable=AsyncMock)
async def test_bot_settings_get_global_exists(mock_find_one):
    existing = BotSettings(key="global", dump_chat_id=123)
    mock_find_one.return_value = existing
    
    doc = await BotSettings.get_global()
    assert doc == existing
    mock_find_one.assert_called_once()

@pytest.mark.asyncio
@patch("models.settings.BotSettings.find_one", new_callable=AsyncMock)
@patch("models.settings.BotSettings.insert", new_callable=AsyncMock)
async def test_bot_settings_get_global_create(mock_insert, mock_find_one):
    mock_find_one.return_value = None
    
    # We patch BotSettings class instantiation check during insert
    with patch.object(BotSettings, "insert", new_callable=AsyncMock) as mock_inst_insert:
        doc = await BotSettings.get_global()
        assert doc.key == "global"
        assert doc.dump_chat_id is None
        mock_find_one.assert_called_once()
        mock_inst_insert.assert_called_once()

@pytest.mark.asyncio
@patch("models.settings.BotSettings.get_global")
async def test_bot_settings_get_dump_chat_id(mock_get_global):
    mock_get_global.return_value = BotSettings(key="global", dump_chat_id=456)
    val = await BotSettings.get_dump_chat_id(fallback=789)
    assert val == 456
    
    mock_get_global.return_value = BotSettings(key="global", dump_chat_id=None)
    val = await BotSettings.get_dump_chat_id(fallback=789)
    assert val == 789
