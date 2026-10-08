import pytest
from pydantic import ValidationError

from app.core.config import Settings

BASE = dict(
    app_env="production",
    postgres_user="u",
    postgres_password="p",
    postgres_db="galactic_production",
    secret_key="x" * 40,
    bcrypt_rounds=12,
)


def make(**override) -> Settings:
    return Settings(_env_file=None, **{**BASE, **override})


def test_valid_production():
    assert make().debug is False


@pytest.mark.parametrize(
    "override",
    [
        {"debug": True},
        {"secret_key": "short"},
        {"secret_key": "change-me-" + "x" * 40},
        {"postgres_db": "galactic_sandbox"},
        {"bcrypt_rounds": 4},
    ],
)
def test_production_rejects_unsafe_settings(override):
    with pytest.raises(ValidationError):
        make(**override)


def test_sandbox_cannot_use_production_db():
    with pytest.raises(ValidationError):
        make(app_env="sandbox")  # db name is galactic_production
