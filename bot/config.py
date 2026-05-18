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


# ── Singleton instance — import this everywhere ───────────────────────────────
settings = Settings()
