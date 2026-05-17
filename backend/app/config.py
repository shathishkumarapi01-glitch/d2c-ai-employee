"""
Application configuration loaded from environment variables.
Uses Pydantic BaseSettings for validation and type coercion.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration — all values sourced from .env or environment."""

    # ── Core ──────────────────────────────────────────────
    environment: str = Field(default="development")
    debug: bool = Field(default=True)
    secret_key: str = Field(default="change-me-to-a-random-secret-key")

    # ── Database (SQLite by default) ──────────────────────
    database_url: str = Field(
        default="sqlite+aiosqlite:///./d2c_warehouse.db",
        validation_alias="DATABASE_URL",
    )

    # ── OpenAI ────────────────────────────────────────────
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini")

    # ── Shopify ───────────────────────────────────────────
    shopify_api_key: str = Field(default="")
    shopify_api_secret: str = Field(default="")
    shopify_store_domain: str = Field(default="")

    # ── Meta Ads ──────────────────────────────────────────
    meta_access_token: str = Field(default="")
    meta_ad_account_id: str = Field(default="")
    meta_app_secret: str = Field(default="")

    # ── Google Sheets ─────────────────────────────────────
    google_sheets_credentials_file: str = Field(default="", validation_alias="GOOGLE_SHEETS_API_KEY")
    google_sheets_spreadsheet_id: str = Field(default="", validation_alias="GOOGLE_SHEETS_SHEET_ID")

    # ── Agent Config ──────────────────────────────────────
    agent_schedule_hours: int = Field(default=6)
    ad_spend_roas_threshold: float = Field(default=2.0)
    ad_spend_min_spend: float = Field(default=1000.0)

    # ── Derived Properties ────────────────────────────────
    @property
    def mock_mode(self) -> bool:
        """Run in mock mode when no OpenAI key is set."""
        return not self.openai_api_key

    @property
    def shopify_mock(self) -> bool:
        return not self.shopify_api_key

    @property
    def meta_mock(self) -> bool:
        return not self.meta_access_token

    @property
    def gsheets_mock(self) -> bool:
        return not self.google_sheets_credentials_file

    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")


# Singleton instance
settings = Settings()
