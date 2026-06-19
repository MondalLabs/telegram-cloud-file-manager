import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock

from bot.api import router, get_current_user, get_admin_user
from models.user import User, UserRole
from models.settings import BotSettings
from bot.config import settings

# Setup Test FastAPI App
app = FastAPI()
app.include_router(router)

# Define mock users
mock_owner = MagicMock(spec=User)
mock_owner.role = UserRole.OWNER
mock_owner.telegram_id = 999

mock_approved = MagicMock(spec=User)
mock_approved.role = UserRole.APPROVED
mock_approved.telegram_id = 123

# Default override behaves as mock_approved
active_user = mock_approved

async def override_get_current_user():
    return active_user

async def override_get_admin_user():
    if active_user.role != UserRole.OWNER:
        raise HTTPException(status_code=403, detail="Requires administrator access")
    return active_user

app.dependency_overrides[get_current_user] = override_get_current_user
app.dependency_overrides[get_admin_user] = override_get_admin_user

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_active_user():
    global active_user
    active_user = mock_approved
    # Clear settings cache back to default
    settings.clear_cache()


# ── 1. Access Gating (Security) ────────────────────────────────────────────────

def test_api_settings_access_denied_for_non_admin():
    global active_user
    active_user = mock_approved  # Role is APPROVED, not OWNER

    response = client.get("/api/admin/settings")
    assert response.status_code == 403
    assert response.json()["detail"] == "Requires administrator access"

    response = client.post("/api/admin/settings", json={"protect_content": True})
    assert response.status_code == 403
    assert response.json()["detail"] == "Requires administrator access"


# ── 2. GET /api/admin/settings ─────────────────────────────────────────────────

@patch("models.settings.BotSettings.get_global", new_callable=AsyncMock)
def test_api_get_settings_success(mock_get_global):
    global active_user
    active_user = mock_owner

    # Set up mock DB settings singleton
    db_set = MagicMock(spec=BotSettings)
    db_set.protect_content = True
    db_set.items_per_page = 25
    db_set.bot_name = "Mock Name Override"
    db_set.auto_delete_hours = 4.5
    mock_get_global.return_value = db_set

    # Force update the cache to make sure they match
    settings.update_cache(
        protect_content=True,
        items_per_page=25,
        bot_name="Mock Name Override",
        auto_delete_hours=4.5
    )

    response = client.get("/api/admin/settings")
    assert response.status_code == 200
    data = response.json()

    assert data["settings"]["protect_content"] is True
    assert data["settings"]["items_per_page"] == 25
    assert data["settings"]["bot_name"] == "Mock Name Override"
    assert data["settings"]["auto_delete_hours"] == 4.5

    assert data["overrides"]["protect_content"] is True
    assert data["overrides"]["items_per_page"] is True
    assert data["overrides"]["bot_name"] is True
    assert data["overrides"]["auto_delete_hours"] is True


# ── 3. POST /api/admin/settings (Validation & Updates) ─────────────────────────

@patch("bot.api.tg_bot")
@patch("models.settings.BotSettings.get_global", new_callable=AsyncMock)
def test_api_post_settings_success(mock_get_global, mock_tg_bot):
    global active_user
    active_user = mock_owner
    mock_tg_bot.is_connected = True
    mock_tg_bot.set_bot_commands = AsyncMock()

    db_set = MagicMock(spec=BotSettings)
    db_set.protect_content = None
    db_set.items_per_page = None
    db_set.bot_name = None
    db_set.auto_delete_hours = None
    db_set.save = AsyncMock()
    mock_get_global.return_value = db_set

    payload = {
        "protect_content": False,
        "items_per_page": 50,
        "bot_name": "New Dynamic Bot",
        "auto_delete_hours": 0.0
    }

    response = client.post("/api/admin/settings", json=payload)
    assert response.status_code == 200
    
    # Assert fields are updated on model and saved
    assert db_set.protect_content is False
    assert db_set.items_per_page == 50
    assert db_set.bot_name == "New Dynamic Bot"
    assert db_set.auto_delete_hours == 0.0
    db_set.save.assert_called_once()

    # Assert cache wrapper holds the new values
    assert settings.protect_content is False
    assert settings.items_per_page == 50
    assert settings.bot_name == "New Dynamic Bot"
    assert settings.auto_delete_hours == 0.0
    assert settings.display_name == "New Dynamic Bot"

    # Assert Telegram commands dynamically refreshed
    mock_tg_bot.set_bot_commands.assert_called_once()


@patch("models.settings.BotSettings.get_global", new_callable=AsyncMock)
def test_api_post_settings_validation_errors(mock_get_global):
    global active_user
    active_user = mock_owner

    db_set = MagicMock(spec=BotSettings)
    mock_get_global.return_value = db_set

    # Test out-of-bounds items_per_page (too low)
    response = client.post("/api/admin/settings", json={"items_per_page": 0})
    assert response.status_code == 400
    assert "Items per page must be between 1 and 100" in response.json()["detail"]

    # Test out-of-bounds items_per_page (too high)
    response = client.post("/api/admin/settings", json={"items_per_page": 101})
    assert response.status_code == 400
    assert "Items per page must be between 1 and 100" in response.json()["detail"]

    # Test out-of-bounds auto_delete_hours (negative)
    response = client.post("/api/admin/settings", json={"auto_delete_hours": -1.0})
    assert response.status_code == 400
    assert "Auto delete hours must be between 0 and 720" in response.json()["detail"]

    # Test out-of-bounds auto_delete_hours (too high, > 30 days)
    response = client.post("/api/admin/settings", json={"auto_delete_hours": 721.0})
    assert response.status_code == 400
    assert "Auto delete hours must be between 0 and 720" in response.json()["detail"]

    # Test long bot name
    response = client.post("/api/admin/settings", json={"bot_name": "x" * 65})
    assert response.status_code == 400
    assert "Bot name must be 64 characters or less" in response.json()["detail"]


@patch("bot.api.tg_bot")
@patch("models.settings.BotSettings.get_global", new_callable=AsyncMock)
def test_api_post_settings_reset_to_default(mock_get_global, mock_tg_bot):
    global active_user
    active_user = mock_owner
    mock_tg_bot.is_connected = False  # Avoid triggering command set

    db_set = MagicMock(spec=BotSettings)
    db_set.protect_content = False
    db_set.items_per_page = 50
    db_set.bot_name = "Custom Bot"
    db_set.auto_delete_hours = 5.0
    db_set.save = AsyncMock()
    mock_get_global.return_value = db_set

    # Force initial values in cache
    settings.update_cache(
        protect_content=False,
        items_per_page=50,
        bot_name="Custom Bot",
        auto_delete_hours=5.0
    )

    # Payload with None (null) resets them to default
    payload = {
        "protect_content": None,
        "items_per_page": None,
        "bot_name": None,
        "auto_delete_hours": None
    }

    response = client.post("/api/admin/settings", json=payload)
    assert response.status_code == 200
    
    assert db_set.protect_content is None
    assert db_set.items_per_page is None
    assert db_set.bot_name is None
    assert db_set.auto_delete_hours is None
    db_set.save.assert_called_once()

    # Cache wrapper should fall back to Pydantic raw values
    assert settings.protect_content == settings._raw_settings.protect_content
    assert settings.items_per_page == settings._raw_settings.items_per_page
    assert settings.bot_name == settings._raw_settings.bot_name
    assert settings.auto_delete_hours == settings._raw_settings.auto_delete_hours
