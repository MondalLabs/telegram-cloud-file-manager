import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from models.state import FSMState
from services.fsm_service import (
    get_state,
    get_data,
    get_state_and_data,
    set_state,
    update_data,
    clear_state
)

@pytest.mark.asyncio
@patch("services.fsm_service.FSMState")
async def test_get_state_exists(mock_state_class):
    doc = MagicMock()
    doc.state = "some_state"
    mock_state_class.find_one = AsyncMock(return_value=doc)
    
    state = await get_state(123)
    assert state == "some_state"

@pytest.mark.asyncio
@patch("services.fsm_service.FSMState")
async def test_get_state_not_exists(mock_state_class):
    mock_state_class.find_one = AsyncMock(return_value=None)
    
    state = await get_state(123)
    assert state is None

@pytest.mark.asyncio
@patch("services.fsm_service.FSMState")
async def test_get_data_exists(mock_state_class):
    doc = MagicMock()
    doc.data = {"key": "val"}
    mock_state_class.find_one = AsyncMock(return_value=doc)
    
    data = await get_data(123)
    assert data == {"key": "val"}

@pytest.mark.asyncio
@patch("services.fsm_service.FSMState")
async def test_get_data_not_exists(mock_state_class):
    mock_state_class.find_one = AsyncMock(return_value=None)
    
    data = await get_data(123)
    assert data == {}

@pytest.mark.asyncio
@patch("services.fsm_service.FSMState")
async def test_get_state_and_data_exists(mock_state_class):
    doc = MagicMock()
    doc.state = "state"
    doc.data = {"d": 1}
    mock_state_class.find_one = AsyncMock(return_value=doc)
    
    state, data = await get_state_and_data(123)
    assert state == "state"
    assert data == {"d": 1}

@pytest.mark.asyncio
@patch("services.fsm_service.FSMState")
async def test_get_state_and_data_not_exists(mock_state_class):
    mock_state_class.find_one = AsyncMock(return_value=None)
    
    state, data = await get_state_and_data(123)
    assert state is None
    assert data == {}

@pytest.mark.asyncio
@patch("services.fsm_service.FSMState")
async def test_set_state_new(mock_state_class):
    mock_state_class.find_one = AsyncMock(return_value=None)
    
    doc = MagicMock()
    doc.insert = AsyncMock()
    mock_state_class.return_value = doc
    
    res = await set_state(123, "state", {"a": 1})
    assert res == doc
    mock_state_class.assert_called_once_with(telegram_id=123, state="state", data={"a": 1})
    doc.insert.assert_called_once()

@pytest.mark.asyncio
@patch("services.fsm_service.FSMState")
async def test_set_state_existing(mock_state_class):
    existing = MagicMock()
    existing.save = AsyncMock()
    mock_state_class.find_one = AsyncMock(return_value=existing)
    
    res = await set_state(123, "state_new", {"a": 2})
    assert res == existing
    assert existing.state == "state_new"
    assert existing.data == {"a": 2}
    existing.save.assert_called_once()

@pytest.mark.asyncio
@patch("services.fsm_service.FSMState")
async def test_update_data_new(mock_state_class):
    mock_state_class.find_one = AsyncMock(return_value=None)
    
    doc = MagicMock()
    doc.insert = AsyncMock()
    mock_state_class.return_value = doc
    
    await update_data(123, val=9)
    mock_state_class.assert_called_once_with(telegram_id=123, state=None, data={"val": 9})
    doc.insert.assert_called_once()

@pytest.mark.asyncio
@patch("services.fsm_service.FSMState")
async def test_update_data_existing(mock_state_class):
    existing = MagicMock()
    existing.data = {"old": 1}
    existing.save = AsyncMock()
    mock_state_class.find_one = AsyncMock(return_value=existing)
    
    await update_data(123, new=2)
    assert existing.data == {"old": 1, "new": 2}
    existing.save.assert_called_once()

@pytest.mark.asyncio
@patch("services.fsm_service.FSMState")
async def test_clear_state_exists(mock_state_class):
    doc = MagicMock()
    doc.delete = AsyncMock()
    mock_state_class.find_one = AsyncMock(return_value=doc)
    
    await clear_state(123)
    doc.delete.assert_called_once()

@pytest.mark.asyncio
@patch("services.fsm_service.FSMState")
async def test_clear_state_not_exists(mock_state_class):
    mock_state_class.find_one = AsyncMock(return_value=None)
    await clear_state(123)  # verify no exception is thrown
