"""Tests for validation utilities."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vbot.db.models import DBUser
from vbot.lib.exceptions import UserNotLinkedError
from vbot.lib.validation import empty_string_to_none, get_valid_linked_db_user

pytestmark = pytest.mark.anyio


class TestGetValidLinkedDbUser:
    """Tests for get_valid_linked_db_user()."""

    async def test_success(self, db):
        """Verify returns DBUser when linked user exists in DB."""
        # Given: a DBUser exists in the database
        await DBUser.create(
            discord_user_id=123456789,
            api_user_id="user-001",
            name="Test User",
            role="PLAYER",
        )

        # Given: a discord member with matching ID
        discord_user = MagicMock()
        discord_user.id = 123456789
        discord_user.display_name = "Test User"
        discord_user.bot = False

        # When: resolving the linked DB user
        result = await get_valid_linked_db_user(discord_user)

        # Then: the correct DBUser is returned
        assert result.api_user_id == "user-001"
        assert result.discord_user_id == 123456789

    async def test_bot_rejected(self, db):
        """Verify raises UserNotLinkedError for bot users."""
        # Given: a discord user that is a bot
        discord_user = MagicMock()
        discord_user.display_name = "Bot User"
        discord_user.bot = True

        # When/Then: raises UserNotLinkedError
        with pytest.raises(UserNotLinkedError, match="is a bot"):
            await get_valid_linked_db_user(discord_user)

    async def test_not_linked(self, db):
        """Verify raises UserNotLinkedError when no matching user in DB."""
        # Given: no DBUser exists for this discord user
        discord_user = MagicMock()
        discord_user.id = 999999999
        discord_user.display_name = "Unknown User"
        discord_user.bot = False

        # When/Then: raises UserNotLinkedError
        with pytest.raises(UserNotLinkedError, match="not linked"):
            await get_valid_linked_db_user(discord_user)

    async def test_no_api_user_id(self, db):
        """Verify raises UserNotLinkedError when DBUser has no api_user_id."""
        # Given: a DBUser exists but with no api_user_id
        await DBUser.create(
            discord_user_id=123456789,
            api_user_id=None,
            name="Test User",
            role="PLAYER",
        )

        # Given: a discord member with matching ID
        discord_user = MagicMock()
        discord_user.id = 123456789
        discord_user.display_name = "Test User"
        discord_user.bot = False

        # When/Then: raises UserNotLinkedError
        with pytest.raises(UserNotLinkedError, match="not linked"):
            await get_valid_linked_db_user(discord_user)


class TestEmptyStringToNone:
    """Tests for empty_string_to_none()."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("", None),
            ("   ", None),
            ("\t\n", None),
            ("hello", "hello"),
            ("  spaced  ", "  spaced  "),
        ],
    )
    def test_empty_string_to_none(self, value, expected):
        """Verify empty/whitespace strings return None, non-empty strings pass through."""
        assert empty_string_to_none(value) == expected
