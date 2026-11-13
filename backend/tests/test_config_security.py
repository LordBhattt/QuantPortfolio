import logging

import pytest
from pydantic import ValidationError

from backend.config import Settings


def test_placeholder_secret_refused_outside_development():
    with pytest.raises(ValidationError, match="SECRET_KEY is missing"):
        Settings(_env_file=None, APP_ENV="test")


def test_development_mode_generates_random_secret(caplog):
    with caplog.at_level(logging.WARNING, logger="backend.config"):
        settings = Settings(_env_file=None, APP_ENV="development", SECRET_KEY="")

    assert len(settings.SECRET_KEY) >= 64
    assert "Sessions will not survive restarts" in caplog.text


def test_real_secret_is_accepted():
    secret = "a-real-secret-that-is-not-a-public-placeholder"
    settings = Settings(_env_file=None, APP_ENV="production", SECRET_KEY=secret)

    assert settings.SECRET_KEY == secret
