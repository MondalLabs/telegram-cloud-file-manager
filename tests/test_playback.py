import pytest
from unittest.mock import AsyncMock, patch
from services.auto_delete_service import _auto_delete_msg

@pytest.mark.asyncio
@patch("services.auto_delete_service.AutoDeleteJob.find_one", new_callable=AsyncMock)
async def test_auto_delete_msg_success(mock_find_one):
    client = AsyncMock()
    mock_find_one.return_value = None

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await _auto_delete_msg(client, 12345, 67890, 5)

        mock_sleep.assert_awaited_once_with(5)
        client.delete_messages.assert_awaited_once_with(12345, 67890)

@pytest.mark.asyncio
@patch("services.auto_delete_service.AutoDeleteJob.find_one", new_callable=AsyncMock)
async def test_auto_delete_msg_exception(mock_find_one):
    client = AsyncMock()
    client.delete_messages.side_effect = Exception("Message too old")
    mock_find_one.return_value = None

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        # Should not raise an exception
        await _auto_delete_msg(client, 12345, 67890, 5)

        mock_sleep.assert_awaited_once_with(5)
        client.delete_messages.assert_awaited_once_with(12345, 67890)
