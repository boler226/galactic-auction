"""Application settings.

The environment is chosen with APP_ENV (sandbox | production | test) and the
values come from .env.<APP_ENV>. Real environment variables always win over
the file, so Docker/CI can override anything.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["sandbox", "production", "test"] = "sandbox"
    app_name: str = "Galactic Auction"
    debug: bool = False

    # PostgreSQL: no defaults for credentials and DB name on purpose
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_url: str | None = None  # full URL override

    # Security: must come from the environment, never from code
    secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    bcrypt_rounds: int = 12

    # Only for `python -m app.cli seed-demo` (sandbox)
    demo_password: str | None = None

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def database_url(self) -> str:
        if self.db_url:
            return self.db_url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @model_validator(mode="after")
    def check_environment(self) -> "Settings":
        problems: list[str] = []
        if self.is_production:
            if self.debug:
                problems.append("DEBUG must be false in production")
            if len(self.secret_key) < 32 or "change-me" in self.secret_key:
                problems.append("SECRET_KEY must be a real key of 32+ characters")
            if "sandbox" in self.postgres_db:
                problems.append("production must not use a sandbox database")
            if self.bcrypt_rounds < 12:
                problems.append("BCRYPT_ROUNDS must be >= 12 in production")
        elif self.app_env == "sandbox" and "production" in self.postgres_db:
            problems.append("sandbox must not use a production database")
        if problems:
            raise ValueError("; ".join(problems))
        return self


@lru_cache
def get_settings() -> Settings:
    env = os.getenv("APP_ENV", "sandbox")
    return Settings(_env_file=BASE_DIR / f".env.{env}")


settings = get_settings()
