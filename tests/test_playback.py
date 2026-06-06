import pytest
from unittest.mock import AsyncMock, patch
from handlers.playback import _auto_delete_msg

@pytest.mark.asyncio
async def test_auto_delete_msg_success():
    client = AsyncMock()

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await _auto_delete_msg(client, 12345, 67890, 5)

        mock_sleep.assert_awaited_once_with(5)
        client.delete_messages.assert_awaited_once_with(12345, 67890)

@pytest.mark.asyncio
async def test_auto_delete_msg_exception():
    client = AsyncMock()
    client.delete_messages.side_effect = Exception("Message too old")

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        # Should not raise an exception
        await _auto_delete_msg(client, 12345, 67890, 5)

        mock_sleep.assert_awaited_once_with(5)
        client.delete_messages.assert_awaited_once_with(12345, 67890)
