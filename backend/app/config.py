from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "test"
    database_url: str = "sqlite+pysqlite:///:memory:"
    ingest_bearer_key: SecretStr | None = None
    ingest_tenant_id: str | None = None
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
