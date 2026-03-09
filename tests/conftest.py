"""Shared test fixtures for the valentina-discord test suite."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from tortoise.contrib.test import tortoise_test_context
from vclient.testing import FakeVClient


def pytest_configure() -> None:
    """Provide fallback environment variables so Settings() can instantiate during collection."""
    _defaults = {
        "VALBOT_DISCORD__TOKEN": "test-token",
        "VALBOT_DISCORD__GUILDS": "111",
        "VALBOT_DISCORD__OWNER_IDS": "222",
        "VALBOT_DISCORD__OWNER_CHANNELS": "333",
        "VALBOT_API__BASE_URL": "http://localhost:8000",
        "VALBOT_API__API_KEY": "test-key",
        "VALBOT_API__DEFAULT_COMPANY_ID": "test-company",
    }
    for key, value in _defaults.items():
        os.environ.setdefault(key, value)


@pytest.fixture
def anyio_backend():
    """Force asyncio backend for Tortoise ORM compatibility."""
    return "asyncio"


@pytest.fixture
async def db():
    """Provide an isolated in-memory SQLite database for each test."""
    async with tortoise_test_context(
        ["vbot.db.models"],
        db_url="sqlite://:memory:",
        app_label="vbot",
    ) as ctx:
        yield ctx


# ---------------------------------------------------------------------------
# FakeVClient fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def fake_vclient():
    """Provide a FakeVClient that intercepts all vclient HTTP calls."""
    async with FakeVClient() as client:
        yield client


# ---------------------------------------------------------------------------
# Discord mock factories
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_discord_member():
    """Create a MagicMock mimicking discord.Member."""
    member = MagicMock()
    member.id = 123456789
    member.name = "testuser"
    member.display_name = "Test User"
    member.bot = False
    member.global_name = "Test User"
    member.discriminator = "0"
    member.avatar = MagicMock()
    member.avatar.key = "abc123"
    member.avatar.url = "https://cdn.discordapp.com/avatars/123456789/abc123.png"
    member.guild = MagicMock()
    member.roles = []
    member.guild_permissions = MagicMock()
    return member


@pytest.fixture
def mock_discord_guild():
    """Create a MagicMock mimicking discord.Guild."""
    guild = MagicMock()
    guild.id = 987654321
    guild.name = "Test Guild"
    guild.channels = []
    guild.roles = []
    guild.members = []
    return guild


@pytest.fixture
def mock_valentina_context(mock_discord_guild):
    """Create an AsyncMock mimicking ValentinaContext."""
    ctx = AsyncMock()
    ctx.get_api_user_id = AsyncMock(return_value="user-001")
    ctx.author = MagicMock()
    ctx.author.id = 123456789
    ctx.author.name = "testuser"
    ctx.guild = mock_discord_guild
    ctx.channel = MagicMock()
    ctx.channel.id = 111222333
    ctx.interaction = MagicMock()
    return ctx


@pytest.fixture
def mock_channel_manager(mocker):
    """Patch ChannelManager to avoid real Discord channel operations."""
    mock_cls = mocker.patch("vbot.lib.channel_mngr.ChannelManager", autospec=True)
    instance = AsyncMock()
    mock_cls.return_value = instance
    return instance
