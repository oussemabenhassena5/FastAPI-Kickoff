import os
import secrets
from typing import Literal

from pydantic import (
    AnyUrl,
    Field,
    PostgresDsn,
    RedisDsn,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.getenv("ENV_FILE", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        secrets_dir="/run/secrets",
    )

    ENVIRONMENT: Literal["local", "staging", "production"] = "local"
    DEBUG: bool = False
    PROJECT_NAME: str = "My FastAPI Project"
    API_STR: str = "/api/v1"

    # Security
    SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(64))
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRES_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRES_DAYS: int = 7
    JWT_ISSUER: str = PROJECT_NAME
    JWT_AUDIENCE: str = "myapp-auth"

    # Database
    DB_ECHO_LOG: bool = False
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 5
    DB_POOL_RECYCLE: int = 3600

    # Security Policy
    MIN_PASSWORD_LENGTH: int = 12
    CORS_ORIGINS: list[str] = []

    # Advanced Rate Limiting
    RATE_LIMIT: str = "100/minute"

    @model_validator(mode="after")
    def validate_environment(self) -> "Settings":
        if self.ENVIRONMENT == "production":
            if self.DEBUG:
                raise ValueError("Debug mode must be disabled in production")
            if any(
                v == "changethis" for v in [self.SECRET_KEY, self.POSTGRES_PASSWORD]
            ):
                raise ValueError("Default secrets forbidden in production")

        return self

    @field_validator("CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )

    # Cache Configuration
    REDIS_URI: RedisDsn | None = None

    # Sentry Configuration
    SENTRY_DSN: AnyUrl | None = None
    SENTRY_ENVIRONMENT: str = ENVIRONMENT

    # Security Headers
    SECURITY_HEADERS: dict = {
        "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Content-Security-Policy": "default-src 'self'",
    }


settings = Settings()
