"""
Application settings using Pydantic Settings.
Loads configuration from environment variables.
"""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings.
    Values are loaded from environment variables or .env file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_ignore_empty=True,
    )

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/teachmewow"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1"
    openai_main_model: str = "gpt-5.2"
    openai_explorer_model: str = "gpt-5.2"
    openai_classifier_model: str = "gpt-5-nano"
    openai_explorer_reasoning_effort: str = "medium"
    openai_explorer_reasoning_summary: str = "auto"

    # HelixDB
    helix_local: bool = True
    helix_port: int = 6969
    helix_api_endpoint: str = ""
    helix_api_key: str = ""
    helix_verbose: bool = False

    # App
    app_env: str = "development"
    debug: bool = True

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, v: str | bool) -> bool:
        """Parse debug value, handling string 'true'/'false' and ignoring invalid values."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            lower = v.lower()
            if lower in ("true", "1", "yes", "on"):
                return True
            if lower in ("false", "0", "no", "off"):
                return False
            # If invalid string (like "WARN"), default to True for development
            return True
        return True

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Uses lru_cache to avoid reading env vars on every call.
    """
    return Settings()
