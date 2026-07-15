import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from beanie import PydanticObjectId

from models.auto_delete import AutoDeleteJob
from services.auto_delete_service import schedule_auto_delete, _auto_delete_msg, hydrate_auto_deletions

# Mock Beanie settings on AutoDeleteJob to avoid CollectionWasNotInitialized during constructor calls in tests
AutoDeleteJob._document_settings = MagicMock()


@pytest.mark.asyncio
@patch("services.auto_delete_service.AutoDeleteJob.insert", new_callable=AsyncMock)
@patch("services.auto_delete_service._auto_delete_msg")
async def test_schedule_auto_delete(mock_auto_delete_msg, mock_insert):
    client = AsyncMock()
    
    # Run scheduling
    await schedule_auto_delete(client, chat_id=1111, message_id=2222, hours=1.5)
    
    mock_insert.assert_called_once()
    mock_auto_delete_msg.assert_called_once_with(client, 1111, 2222, 5400)


@pytest.mark.asyncio
@patch("services.auto_delete_service.AutoDeleteJob.find_one", new_callable=AsyncMock)
async def test_auto_delete_msg_success(mock_find_one):
    client = AsyncMock()
    
    # Mock finding the job and deleting it
    mock_job = AsyncMock(spec=AutoDeleteJob)
    mock_job.delete = AsyncMock()
    mock_find_one.return_value = mock_job
    
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await _auto_delete_msg(client, chat_id=1111, msg_id=2222, delay=5)
        
        mock_sleep.assert_awaited_once_with(5)
        client.delete_messages.assert_awaited_once_with(1111, 2222)
        mock_find_one.assert_called_once()
        mock_job.delete.assert_called_once()


@pytest.mark.asyncio
@patch("services.auto_delete_service.AutoDeleteJob.find_one", new_callable=AsyncMock)
async def test_auto_delete_msg_already_deleted(mock_find_one):
    client = AsyncMock()
    client.delete_messages.side_effect = Exception("Message not found")
    
    mock_job = AsyncMock(spec=AutoDeleteJob)
    mock_job.delete = AsyncMock()
    mock_find_one.return_value = mock_job
    
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        # Should not raise exception
        await _auto_delete_msg(client, chat_id=1111, msg_id=2222, delay=5)
        
        mock_sleep.assert_awaited_once_with(5)
        client.delete_messages.assert_awaited_once_with(1111, 2222)
        mock_find_one.assert_called_once()
        mock_job.delete.assert_called_once()


@pytest.mark.asyncio
@patch("services.auto_delete_service.AutoDeleteJob.find_all")
@patch("services.auto_delete_service._auto_delete_msg")
async def test_hydrate_auto_deletions(mock_auto_delete_msg, mock_find_all):
    client = AsyncMock()
    now = datetime.now(timezone.utc)
    
    # 1. Expired job (scheduled in the past)
    expired_job = MagicMock(spec=AutoDeleteJob)
    expired_job.chat_id = 1111
    expired_job.message_id = 2222
    expired_job.delete_at = now - timedelta(minutes=10)
    expired_job.delete = AsyncMock()
    
    # 2. Future job (scheduled in the future)
    future_job = MagicMock(spec=AutoDeleteJob)
    future_job.chat_id = 3333
    future_job.message_id = 4444
    future_job.delete_at = now + timedelta(minutes=30)
    future_job.delete = AsyncMock()
    
    mock_find_all.return_value.to_list = AsyncMock(return_value=[expired_job, future_job])
    
    await hydrate_auto_deletions(client)
    
    # Expired job should be deleted instantly
    client.delete_messages.assert_awaited_once_with(chat_id=1111, message_ids=2222)
    expired_job.delete.assert_called_once()
    
    # Future job should trigger in-memory _auto_delete_msg task scheduler
    mock_auto_delete_msg.assert_called_once()
    # Arg checking: delay should be roughly 1800 seconds (30 minutes)
    called_args = mock_auto_delete_msg.call_args[0]
    assert called_args[0] == client
    assert called_args[1] == 3333
    assert called_args[2] == 4444
    assert 1700 < called_args[3] < 1900


@pytest.mark.asyncio
@patch("services.auto_delete_service.AutoDeleteJob.find_all")
@patch("services.auto_delete_service._auto_delete_msg")
async def test_hydrate_auto_deletions_timezone_naive(mock_auto_delete_msg, mock_find_all):
    client = AsyncMock()
    # Create naive UTC datetime (no tzinfo)
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    
    # 1. Expired job (scheduled in the past, naive)
    expired_job = MagicMock(spec=AutoDeleteJob)
    expired_job.chat_id = 5555
    expired_job.message_id = 6666
    expired_job.delete_at = now_naive - timedelta(minutes=10) # Naive
    expired_job.delete = AsyncMock()
    
    # 2. Future job (scheduled in the future, naive)
    future_job = MagicMock(spec=AutoDeleteJob)
    future_job.chat_id = 7777
    future_job.message_id = 8888
    future_job.delete_at = now_naive + timedelta(minutes=30) # Naive
    future_job.delete = AsyncMock()
    
    mock_find_all.return_value.to_list = AsyncMock(return_value=[expired_job, future_job])
    
    # This should run without throwing "can't subtract offset-naive and offset-aware datetimes"
    await hydrate_auto_deletions(client)
    
    client.delete_messages.assert_awaited_once_with(chat_id=5555, message_ids=6666)
    expired_job.delete.assert_called_once()
    mock_auto_delete_msg.assert_called_once()
