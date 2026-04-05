"""Application configuration.

Reads environment variables from .env using pydantic-settings.
All other modules import `settings` from here — nothing reads os.environ directly.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # LLM
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"

    # App
    app_name: str = "Multi-Agent Cooking Assistant"
    app_version: str = "0.1.0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Module-level singleton — import this everywhere instead of instantiating Settings() yourself.
settings = Settings()
