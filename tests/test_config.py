"""Tests for configuration utilities."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from vbot.config.base import Settings, string_to_list
from vbot.constants import LogLevel


class TestStringToList:
    """Tests for string_to_list()."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("a,b,c", ["a", "b", "c"]),
            ("one", ["one"]),
            ("", [""]),
            ("a, b, c", ["a", "b", "c"]),
            ("  x , y , z  ", ["x", "y", "z"]),
        ],
    )
    def test_string_to_list(self, value, expected):
        """Verify comma-separated string conversion with whitespace handling."""
        assert string_to_list(value) == expected

    def test_preserves_internal_spaces(self):
        """Verify internal spaces within items are preserved."""
        result = string_to_list("hello world, foo bar")
        assert result == ["hello world", "foo bar"]


class TestSettingsFromEnvVars:
    """Tests for Settings construction from environment variables."""

    def test_minimal_required_env_vars(self, monkeypatch):
        """Verify Settings constructs with required env vars and applies defaults."""
        # Given: only the required env vars are set
        monkeypatch.setenv("VALBOT_DISCORD__TOKEN", "test-token-123")
        monkeypatch.setenv("VALBOT_DISCORD__GUILDS", "111,222")
        monkeypatch.setenv("VALBOT_DISCORD__OWNER_IDS", "333")
        monkeypatch.setenv("VALBOT_DISCORD__OWNER_CHANNELS", "444")
        monkeypatch.setenv("VALBOT_API__BASE_URL", "http://localhost:8000")
        monkeypatch.setenv("VALBOT_API__API_KEY", "test-key")
        monkeypatch.setenv("VALBOT_API__DEFAULT_COMPANY_ID", "company-001")

        # When: constructing Settings
        s = Settings()

        # Then: required fields are populated
        assert s.discord.token == "test-token-123"  # noqa: S105
        assert s.api.base_url == "http://localhost:8000"
        assert s.api.api_key == "test-key"
        assert s.api.default_company_id == "company-001"

        # Then: defaults are applied
        assert s.api.timeout == 10.0
        assert s.api.max_retries == 5
        assert s.api.retry_delay == 1.0
        assert s.api.auto_retry_rate_limit is True
        assert s.api.auto_idempotency_keys is True
        assert s.api.enable_logs is False
        assert s.database_path == Path("data/database.db")
        assert s.log_file_path is None
        assert s.log_level == LogLevel.INFO

    def test_discord_guilds_parsed_as_list(self, monkeypatch):
        """Verify comma-separated GUILDS env var is parsed into a list."""
        # Given: guilds env var with multiple comma-separated values
        monkeypatch.setenv("VALBOT_DISCORD__TOKEN", "t")
        monkeypatch.setenv("VALBOT_DISCORD__GUILDS", "111, 222, 333")
        monkeypatch.setenv("VALBOT_DISCORD__OWNER_IDS", "444")
        monkeypatch.setenv("VALBOT_DISCORD__OWNER_CHANNELS", "555")
        monkeypatch.setenv("VALBOT_API__BASE_URL", "http://localhost")
        monkeypatch.setenv("VALBOT_API__API_KEY", "k")
        monkeypatch.setenv("VALBOT_API__DEFAULT_COMPANY_ID", "c")

        # When: constructing Settings
        s = Settings()

        # Then: guilds is a list of trimmed strings
        assert s.discord.guilds == ["111", "222", "333"]

    def test_owner_ids_parsed_as_list(self, monkeypatch):
        """Verify comma-separated OWNER_IDS env var is parsed into a list."""
        # Given: owner_ids with multiple values
        monkeypatch.setenv("VALBOT_DISCORD__TOKEN", "t")
        monkeypatch.setenv("VALBOT_DISCORD__GUILDS", "111")
        monkeypatch.setenv("VALBOT_DISCORD__OWNER_IDS", "aaa, bbb")
        monkeypatch.setenv("VALBOT_DISCORD__OWNER_CHANNELS", "ccc")
        monkeypatch.setenv("VALBOT_API__BASE_URL", "http://localhost")
        monkeypatch.setenv("VALBOT_API__API_KEY", "k")
        monkeypatch.setenv("VALBOT_API__DEFAULT_COMPANY_ID", "c")

        # When: constructing Settings
        s = Settings()

        # Then: owner_ids is a list of trimmed strings
        assert s.discord.owner_ids == ["aaa", "bbb"]

    def test_optional_overrides(self, monkeypatch):
        """Verify optional fields can be overridden via env vars."""
        # Given: all required + optional env vars
        monkeypatch.setenv("VALBOT_DISCORD__TOKEN", "t")
        monkeypatch.setenv("VALBOT_DISCORD__GUILDS", "111")
        monkeypatch.setenv("VALBOT_DISCORD__OWNER_IDS", "222")
        monkeypatch.setenv("VALBOT_DISCORD__OWNER_CHANNELS", "333")
        monkeypatch.setenv("VALBOT_API__BASE_URL", "http://localhost")
        monkeypatch.setenv("VALBOT_API__API_KEY", "k")
        monkeypatch.setenv("VALBOT_API__DEFAULT_COMPANY_ID", "c")
        monkeypatch.setenv("VALBOT_API__TIMEOUT", "30.0")
        monkeypatch.setenv("VALBOT_API__MAX_RETRIES", "10")
        monkeypatch.setenv("VALBOT_DATABASE_PATH", "/tmp/test.db")  # noqa: S108
        monkeypatch.setenv("VALBOT_LOG_LEVEL", "DEBUG")

        # When: constructing Settings
        s = Settings()

        # Then: overridden values are used
        assert s.api.timeout == 30.0
        assert s.api.max_retries == 10
        assert s.database_path == Path("/tmp/test.db")  # noqa: S108
        assert s.log_level == LogLevel.DEBUG

    def test_missing_required_field_raises(self, monkeypatch):
        """Verify missing required env var raises ValidationError."""
        # Given: all required env vars are removed
        monkeypatch.delenv("VALBOT_DISCORD__TOKEN", raising=False)
        monkeypatch.delenv("VALBOT_DISCORD__GUILDS", raising=False)
        monkeypatch.delenv("VALBOT_DISCORD__OWNER_IDS", raising=False)
        monkeypatch.delenv("VALBOT_DISCORD__OWNER_CHANNELS", raising=False)
        monkeypatch.delenv("VALBOT_API__BASE_URL", raising=False)
        monkeypatch.delenv("VALBOT_API__API_KEY", raising=False)
        monkeypatch.delenv("VALBOT_API__DEFAULT_COMPANY_ID", raising=False)

        # When/Then: constructing Settings raises ValidationError
        with pytest.raises(ValidationError, match="Field required"):
            Settings()
