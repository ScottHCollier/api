from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL, make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "final_third"
    postgres_user: str = "final_third"
    postgres_password: SecretStr = SecretStr("final_third_dev")
    database_url_override: str | None = Field(
        default=None, validation_alias="DATABASE_URL"
    )
    seed_on_startup: bool = False
    auth_secret: SecretStr = SecretStr("change-this-development-auth-secret")
    access_token_expire_minutes: int = 60
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://montpellier-fc.localhost:3000",
        "http://oakwood-united.localhost:3000",
    ]
    fa_import_enabled: bool = True
    fa_import_interval_seconds: int = 86400
    fa_request_timeout_seconds: int = 20
    object_storage_endpoint: str = "http://localhost:9000"
    object_storage_region: str = "us-east-1"
    object_storage_bucket: str = "final-third-media"
    object_storage_private_bucket: str = "final-third-private"
    object_storage_access_key: str = "final-third-dev"
    object_storage_secret_key: SecretStr = SecretStr("final-third-dev-secret")
    object_storage_public_base_url: str = "http://localhost:9000/final-third-media"
    app_base_url: str = "http://localhost:3000"
    resend_api_key: SecretStr | None = None
    email_from: str | None = None
    resend_audience_id: str | None = None

    @property
    def database_url(self) -> URL:
        if self.database_url_override:
            url = make_url(self.database_url_override)
            # Render supplies a plain postgres:// URL. This project uses the
            # psycopg v3 driver, so make the driver explicit for SQLAlchemy
            # and Alembic instead of falling back to psycopg2.
            if url.drivername in {"postgres", "postgresql"}:
                url = url.set(drivername="postgresql+psycopg")
            return url
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
