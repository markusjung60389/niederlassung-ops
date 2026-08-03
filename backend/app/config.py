from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_timezone: str = "Europe/Berlin"
    app_branch_default: str = "Remscheid"
    database_url: str = "sqlite:///./remscheid_ops.db"
    uploads_dir: str = "/app/uploads"
    hermes_api_base_url: str | None = None
    hermes_api_key: str | None = None
    hermes_agent_model: str = "hermes-agent"
    hermes_timeout_seconds: float = Field(default=20.0, ge=1.0, le=120.0)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
