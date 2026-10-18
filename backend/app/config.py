from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="XAU_", extra="ignore")

    database_url: str = "postgresql+psycopg://xau:xau@localhost:5432/xau_lab"
    secret_key: str = Field(default="dev-only-change-me-0123456789abcdef", min_length=32)
    session_hours: int = 12
    cookie_secure: bool = False
    # Upload limits
    max_script_bytes: int = 1_000_000
    max_zip_bytes: int = 20_000_000
    max_zip_members: int = 500
    max_zip_uncompressed_bytes: int = 100_000_000
    login_attempts_per_minute: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
