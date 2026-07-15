import pytest
import hmac
import hashlib
import json
import time
from urllib.parse import urlencode
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException
from beanie import PydanticObjectId

from utils.auth import verify_telegram_init_data
from bot.api import get_current_user, get_admin_user
from models.user import UserRole

# ── Part 1: Unit tests for verify_telegram_init_data ───────────────────────

def test_verify_telegram_init_data_success():
    bot_token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    user_data = {"id": 12345, "first_name": "Test User", "username": "testuser"}
    auth_date = int(time.time())
    
    # Sort keys alphabetically and prepare check string
    data_dict = {
        "auth_date": str(auth_date),
        "user": json.dumps(user_data)
    }
    
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data_dict.items()))
    
    # Calculate secret key and hash signature
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    
    # Add hash to query parameters
    data_dict["hash"] = expected_hash
    init_data_qs = urlencode(data_dict)
    
    is_valid, parsed_user = verify_telegram_init_data(init_data_qs, bot_token)
    assert is_valid is True
    assert parsed_user["id"] == 12345
    assert parsed_user["first_name"] == "Test User"

def test_verify_telegram_init_data_expired():
    bot_token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    user_data = {"id": 12345}
    auth_date = int(time.time()) - 90000  # More than 24 hours ago (86400 seconds)
    
    data_dict = {
        "auth_date": str(auth_date),
        "user": json.dumps(user_data)
    }
    
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data_dict.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    
    data_dict["hash"] = expected_hash
    init_data_qs = urlencode(data_dict)
    
    # Expired check
    is_valid, _ = verify_telegram_init_data(init_data_qs, bot_token)
    assert is_valid is False

def test_verify_telegram_init_data_invalid_hash():
    bot_token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    user_data = {"id": 12345}
    auth_date = int(time.time())
    
    data_dict = {
        "auth_date": str(auth_date),
        "user": json.dumps(user_data),
        "hash": "wronghashhere"
    }
    init_data_qs = urlencode(data_dict)
    
    is_valid, _ = verify_telegram_init_data(init_data_qs, bot_token)
    assert is_valid is False

def test_verify_telegram_init_data_missing_hash():
    is_valid, _ = verify_telegram_init_data("auth_date=12345", "token")
    assert is_valid is False

def test_verify_telegram_init_data_missing_auth_date():
    is_valid, _ = verify_telegram_init_data("hash=123", "token")
    assert is_valid is False

def test_verify_telegram_init_data_invalid_auth_date_format():
    is_valid, _ = verify_telegram_init_data("hash=123&auth_date=not_an_int", "token")
    assert is_valid is False

def test_verify_telegram_init_data_missing_user():
    bot_token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    auth_date = int(time.time())
    data_dict = {
        "auth_date": str(auth_date),
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data_dict.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    data_dict["hash"] = expected_hash
    init_data_qs = urlencode(data_dict)
    
    is_valid, _ = verify_telegram_init_data(init_data_qs, bot_token)
    assert is_valid is False

def test_verify_telegram_init_data_invalid_user_json():
    bot_token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    auth_date = int(time.time())
    data_dict = {
        "auth_date": str(auth_date),
        "user": "{invalid json"
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data_dict.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    data_dict["hash"] = expected_hash
    init_data_qs = urlencode(data_dict)
    
    is_valid, _ = verify_telegram_init_data(init_data_qs, bot_token)
    assert is_valid is False

def test_verify_telegram_init_data_exception_on_parse():
    is_valid, _ = verify_telegram_init_data(12345, "token")
    assert is_valid is False

# ── Part 2: FastAPI Dependency Injection Tests ──────────────────────────────

@pytest.mark.anyio
@patch("bot.api.verify_telegram_init_data")
@patch("services.user_service.get_or_create")
async def test_get_current_user_valid(mock_get_or_create, mock_verify):
    mock_verify.return_value = (True, {"id": 999, "first_name": "API User", "username": "apiuser"})
    
    # Mock user object returned by service
    fake_user = MagicMock()
    fake_user.telegram_id = 999
    fake_user.role = UserRole.APPROVED
    mock_get_or_create.return_value = fake_user
    
    user = await get_current_user(x_telegram_init_data="dummy_init_data")
    
    assert user.telegram_id == 999
    assert user.role == UserRole.APPROVED
    from bot.config import settings
    mock_verify.assert_called_once_with("dummy_init_data", settings.bot_token)
    mock_get_or_create.assert_called_once_with(telegram_id=999, full_name="API User", username="apiuser")

@pytest.mark.anyio
@patch("bot.api.verify_telegram_init_data")
async def test_get_current_user_invalid_signature(mock_verify):
    mock_verify.return_value = (False, {})
    
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(x_telegram_init_data="bad_init_data")
        
    assert exc_info.value.status_code == 401
    assert "Invalid signature" in exc_info.value.detail

@pytest.mark.anyio
@patch("bot.api.verify_telegram_init_data")
@patch("services.user_service.get_or_create")
async def test_get_current_user_guest_denied(mock_get_or_create, mock_verify):
    mock_verify.return_value = (True, {"id": 999, "first_name": "API User"})
    
    fake_user = MagicMock()
    fake_user.telegram_id = 999
    fake_user.role = UserRole.GUEST
    mock_get_or_create.return_value = fake_user
    
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(x_telegram_init_data="dummy_init_data")
        
    assert exc_info.value.status_code == 403
    assert "Access denied" in exc_info.value.detail

@pytest.mark.anyio
async def test_get_admin_user_owner():
    fake_user = MagicMock()
    fake_user.role = UserRole.OWNER
    
    admin_user = await get_admin_user(user=fake_user)
    assert admin_user == fake_user

@pytest.mark.anyio
async def test_get_admin_user_non_owner():
    fake_user = MagicMock()
    fake_user.role = UserRole.APPROVED
    
    with pytest.raises(HTTPException) as exc_info:
        await get_admin_user(user=fake_user)
        
    assert exc_info.value.status_code == 403
    assert "Requires administrator access" in exc_info.value.detail
