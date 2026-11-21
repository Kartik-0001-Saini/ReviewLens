"""Application settings, read from environment variables (and a local .env file in development)."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    # The key is only ever read here, on the server. The browser never sees it.
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    # gpt-oss "thinks" before answering; "low" keeps hidden tokens down (fewer 429s on the free tier).
    # Set it to an empty value for models without reasoning.
    groq_reasoning_effort: str = "low"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_timeout_seconds: float = 60.0

    batch_size: int = Field(default=5, ge=1, le=20)
    max_retries: int = Field(default=4, ge=0, le=8)
    max_upload_bytes: int = 2_000_000

    db_path: Path = PROJECT_ROOT / "backend" / "data" / "reviewlens.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
