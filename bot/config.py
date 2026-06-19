"""
bot/config.py
─────────────────────────────────────────────────────────────────────────────
Centralised configuration loaded from environment variables / .env file.
Uses Pydantic Settings so every value is type-validated at startup.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """All runtime configuration for the bot."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── MTProto credentials (from my.telegram.org + @BotFather) ────────────
    api_id: int = Field(..., alias="API_ID")
    api_hash: str = Field(..., alias="API_HASH")
    bot_token: str = Field(..., alias="BOT_TOKEN")

    # ── Database ─────────────────────────────────────────────────────────────
    mongo_uri: str = Field(..., alias="MONGO_URI")

    # ── Telegram IDs ─────────────────────────────────────────────────────────
    # DUMP_CHAT_ID is optional at deploy time — auto-detected via /setup command
    dump_chat_id: int | None = Field(default=None, alias="DUMP_CHAT_ID")
    owner_id: int = Field(..., alias="OWNER_ID")

    # ── UI ───────────────────────────────────────────────────────────────────
    items_per_page: int = Field(default=15, alias="ITEMS_PER_PAGE")

    # ── Render health server ─────────────────────────────────────────────────
    health_port: int = Field(default=10000, alias="HEALTH_PORT")

    # ── Personalisation ──────────────────────────────────────────────────────
    # Display name shown in welcome / denial messages. Leave blank for generic.
    bot_name: str | None = Field(default=None, alias="BOT_NAME")

    # ── Security / DRM ───────────────────────────────────────────────────────
    # Set to false to allow users to forward and save delivered files.
    protect_content: bool = Field(default=True, alias="PROTECT_CONTENT")
    # Hours after which a delivered file is deleted from the user's chat.
    # 0 = never auto-delete.
    auto_delete_hours: float = Field(default=1.0, alias="AUTO_DELETE_HOURS")

    # ── Derived helpers ───────────────────────────────────────────────────────
    @property
    def db_name(self) -> str:
        """Extract database name from the MongoDB URI, fallback to 'cfm_db'."""
        try:
            path = self.mongo_uri.split("/")[-1].split("?")[0]
            return path if path else "cfm_db"
        except Exception:
            return "cfm_db"

    @property
    def display_name(self) -> str | None:
        """
        Returns the configured bot name, stripped of whitespace.
        Returns None if BOT_NAME is not set or is blank.
        Handlers use this to decide between branded and generic text.
        """
        return self.bot_name.strip() if self.bot_name and self.bot_name.strip() else None


class LiveSettings:
    """Wrapper class around the Pydantic Settings instance that supports in-memory overrides."""

    def __init__(self, raw_settings: Settings):
        self._raw_settings = raw_settings
        self._cache = {}

    def update_cache(
        self,
        protect_content: bool | None = None,
        items_per_page: int | None = None,
        bot_name: str | None = None,
        auto_delete_hours: float | None = None,
    ):
        """Update settings override cache. Storing None resets to env defaults."""
        self._cache["protect_content"] = protect_content
        self._cache["items_per_page"] = items_per_page
        self._cache["bot_name"] = bot_name
        self._cache["auto_delete_hours"] = auto_delete_hours

    def clear_cache(self):
        """Clears all live settings overrides."""
        self._cache.clear()

    @property
    def protect_content(self) -> bool:
        val = self._cache.get("protect_content")
        return val if val is not None else self._raw_settings.protect_content

    @property
    def items_per_page(self) -> int:
        val = self._cache.get("items_per_page")
        return val if val is not None else self._raw_settings.items_per_page

    @property
    def bot_name(self) -> str | None:
        val = self._cache.get("bot_name")
        return val if val is not None else self._raw_settings.bot_name

    @property
    def auto_delete_hours(self) -> float:
        val = self._cache.get("auto_delete_hours")
        return val if val is not None else self._raw_settings.auto_delete_hours

    @property
    def display_name(self) -> str | None:
        name = self.bot_name
        return name.strip() if name and name.strip() else None

    def __getattr__(self, name):
        """Delegate any other attribute queries to the underlying Settings singleton."""
        return getattr(self._raw_settings, name)


# ── Singleton instance — import this everywhere ───────────────────────────────
settings = LiveSettings(Settings())
