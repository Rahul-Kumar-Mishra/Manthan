from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Manthan Hospital Management System"
    app_version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://manthan:local_dev_password@localhost:5432/manthan"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "development-only-insecure-secret-key-change-me"
    access_token_expire_minutes: int = 30

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
