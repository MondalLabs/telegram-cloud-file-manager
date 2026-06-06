import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pyrogram.types import CallbackQuery, User as PyrogramUser
from models.user import User, UserRole
from handlers.playback import play_video
from beanie import PydanticObjectId

@pytest.mark.asyncio
async def test_play_video_missing_file():
    """Test play_video when the requested file does not exist (file_doc is None)."""
    # 1. Setup mocks
    client = AsyncMock()

    # Mock Pyrogram CallbackQuery
    query = AsyncMock(spec=CallbackQuery)
    # The answer method should be awaitable (AsyncMock)
    query.answer = AsyncMock()
    query.data = b"dummy_data"

    # We must patch from_user and properties correctly
    query.from_user = MagicMock(spec=PyrogramUser)
    query.from_user.id = 12345
    query.from_user.first_name = "Test"
    query.from_user.username = "testuser"

    # Let's also patch the user service so the decorator doesn't do real DB calls
    with patch("handlers.playback.decode", return_value=["play", "60a7b0b9b3a3a3a3a3a3a3a3"]):
        with patch("handlers.playback.file_service.get_file", new_callable=AsyncMock) as mock_get_file:
            with patch("middlewares.access_control.user_service.get_or_create", new_callable=AsyncMock) as mock_user_service:
                # Mock get_or_create to return an approved user
                mock_user = MagicMock(spec=User)
                mock_user.role = UserRole.APPROVED
                mock_user_service.return_value = mock_user

                # 2. Configure mock to simulate file not found
                mock_get_file.return_value = None

                # 3. Execute
                await play_video(client, query) # Notice we don't pass user, the decorator does it

                # 4. Verify
                # Should show alert
                query.answer.assert_any_call("❌ File not found \u2014 it may have been deleted.", show_alert=True)
                # The get_file should have been called with the PydanticObjectId
                mock_get_file.assert_called_once_with(PydanticObjectId("60a7b0b9b3a3a3a3a3a3a3a3"))


@pytest.mark.asyncio
async def test_play_video_invalid_id():
    """Test play_video when the requested file ID is invalid (raises Exception)."""
    # 1. Setup mocks
    client = AsyncMock()
    query = AsyncMock(spec=CallbackQuery)
    query.answer = AsyncMock()

    query.data = b"dummy_data"
    query.from_user = MagicMock(spec=PyrogramUser)
    query.from_user.id = 12345
    query.from_user.first_name = "Test"
    query.from_user.username = "testuser"

    with patch("handlers.playback.decode", return_value=["play", "invalid_id"]):
        with patch("handlers.playback.file_service.get_file", new_callable=AsyncMock) as mock_get_file:
            with patch("middlewares.access_control.user_service.get_or_create", new_callable=AsyncMock) as mock_user_service:
                # Mock get_or_create to return an approved user
                mock_user = MagicMock(spec=User)
                mock_user.role = UserRole.APPROVED
                mock_user_service.return_value = mock_user

                # 2. Configure mock to simulate exception
                mock_get_file.side_effect = Exception("Invalid ID format")

                # 3. Execute
                await play_video(client, query)

                # 4. Verify
                query.answer.assert_any_call("❌ Invalid file ID.", show_alert=True)
