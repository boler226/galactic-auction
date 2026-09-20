"""Application settings loaded from environment variables / .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Galactic Auction"
    debug: bool = False

    # PostgreSQL connection parameters
    postgres_user: str = "auction"
    postgres_password: str = "auction"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "galactic_auction"

    # Connection pool (important for high-load scenarios)
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # Optional full URL override (e.g. for tests or managed databases)
    db_url: str | None = None

    @property
    def database_url(self) -> str:
        if self.db_url:
            return self.db_url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
