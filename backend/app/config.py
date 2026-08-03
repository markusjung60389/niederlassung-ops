from datetime import timezone
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AuthMode = Literal["dev", "azure_ad"]


class Settings(BaseSettings):
    app_env: str = "development"
    app_timezone: str = "Europe/Berlin"
    app_branch_default: str = "Remscheid"
    database_url: str = "sqlite:///./remscheid_ops.db"
    uploads_dir: str = "/app/uploads"

    # Comma separated list. A wildcard is refused because the API sends credentials.
    cors_allow_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3500,http://127.0.0.1:3500"

    # "dev"      -> caller identifies itself via X-User-Id, refused when APP_ENV is production.
    # "azure_ad" -> Microsoft Entra ID bearer tokens are validated on every request.
    auth_mode: AuthMode = "dev"
    # Optional convenience for local work: used when no X-User-Id header is sent.
    auth_dev_default_user_id: str | None = None

    # --- Microsoft Entra ID (Azure AD) -------------------------------------
    # Prepared but inactive while auth_mode is "dev". See docs/azure-ad-setup.md.
    azure_tenant_id: str | None = None
    azure_client_id: str | None = None
    # Defaults to "api://{azure_client_id}" and the bare client id when left empty.
    azure_api_audience: str | None = None
    azure_authority_host: str = "https://login.microsoftonline.com"
    azure_jwks_cache_seconds: int = Field(default=3600, ge=60, le=86400)
    # Claim carrying the app roles issued by Entra ID.
    azure_role_claim: str = "roles"
    # Maps an Entra app role or group object id to a role name in the roles table.
    # Format: "OpsManager=Niederlassungsleiter,<group-uuid>=HSE / Compliance"
    azure_role_map: str = ""
    # Create a local user row on first successful login.
    azure_auto_provision_users: bool = True
    # Role name assigned to auto provisioned users without a mapped role.
    azure_default_role_name: str | None = None
    # Clock skew tolerance for token validation, in seconds.
    azure_leeway_seconds: int = Field(default=60, ge=0, le=300)

    # --- Uploads ----------------------------------------------------------
    upload_max_bytes: int = Field(default=25 * 1024 * 1024, ge=1024, le=200 * 1024 * 1024)
    upload_allowed_extensions: str = ".pdf,.png,.jpg,.jpeg,.gif,.webp,.txt,.csv,.doc,.docx,.xls,.xlsx,.odt,.ods,.msg,.eml"

    # --- Worker -----------------------------------------------------------
    # Interval for the recurrence roll-over and escalation job.
    worker_interval_seconds: int = Field(default=900, ge=30, le=86400)

    hermes_api_base_url: str | None = None
    hermes_api_key: str | None = None
    hermes_agent_model: str = "hermes-agent"
    hermes_timeout_seconds: float = Field(default=20.0, ge=1.0, le=120.0)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() in {"production", "prod"}

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]

    @property
    def allowed_extensions(self) -> set[str]:
        return {
            item.strip().lower() if item.strip().startswith(".") else f".{item.strip().lower()}"
            for item in self.upload_allowed_extensions.split(",")
            if item.strip()
        }

    @property
    def timezone(self):
        """Local timezone for due-date arithmetic; falls back to UTC if unknown."""
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            return ZoneInfo(self.app_timezone)
        except (ZoneInfoNotFoundError, ValueError):
            return timezone.utc

    @property
    def azure_authority(self) -> str:
        return f"{self.azure_authority_host.rstrip('/')}/{self.azure_tenant_id}"

    @property
    def azure_jwks_url(self) -> str:
        return f"{self.azure_authority}/discovery/v2.0/keys"

    @property
    def azure_issuers(self) -> list[str]:
        """Entra ID issues v2.0 and, for some flows, v1.0 tokens with different issuer values."""
        return [
            f"{self.azure_authority}/v2.0",
            f"https://sts.windows.net/{self.azure_tenant_id}/",
        ]

    @property
    def azure_audiences(self) -> list[str]:
        if self.azure_api_audience:
            return [self.azure_api_audience]
        return [f"api://{self.azure_client_id}", str(self.azure_client_id)]

    @property
    def azure_role_mapping(self) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for entry in self.azure_role_map.split(","):
            key, separator, value = entry.partition("=")
            if separator and key.strip() and value.strip():
                mapping[key.strip()] = value.strip()
        return mapping

    @model_validator(mode="after")
    def _validate(self) -> "Settings":
        if "*" in self.cors_origins:
            raise ValueError(
                "CORS_ALLOW_ORIGINS must not contain '*': the API sends credentials and a wildcard "
                "origin would expose personal data to any website."
            )
        if self.auth_mode == "dev" and self.is_production:
            raise ValueError(
                "AUTH_MODE=dev is refused when APP_ENV is production. "
                "Set AUTH_MODE=azure_ad and configure AZURE_TENANT_ID / AZURE_CLIENT_ID."
            )
        if self.auth_mode == "azure_ad" and not (self.azure_tenant_id and self.azure_client_id):
            raise ValueError("AUTH_MODE=azure_ad requires AZURE_TENANT_ID and AZURE_CLIENT_ID.")
        return self


settings = Settings()
