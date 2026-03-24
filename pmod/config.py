"""Application configuration loaded from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global settings sourced from .env file."""

    schwab_app_key: str = ""
    schwab_app_secret: str = ""
    schwab_callback_url: str = "https://127.0.0.1:8182/callback"
    schwab_token_path: Path = Path("schwab_token.json")

    polygon_api_key: str = ""
    alpha_vantage_api_key: str = ""

    database_url: str = "sqlite:///pmod.db"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
