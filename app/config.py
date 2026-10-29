from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./taskflow.db"
    redis_url: str = "redis://localhost:6379/0"
    session_idle_hours: int = 24
    session_max_days: int = 30
    session_touch_minutes: int = 5
    bcrypt_rounds: int = 12


@lru_cache
def get_settings() -> Settings:
    return Settings()
