"""Tests for the user API handler."""

from __future__ import annotations

import pytest
from vclient.models import DiscordProfile
from vclient.testing import Routes, UserFactory

from vbot.db.models import DBUser
from vbot.handlers.user import user_api_handler
from vbot.lib.exceptions import ValidationError

pytestmark = pytest.mark.anyio

_DISCORD_PROFILE = DiscordProfile(
    id="123456789", username="testuser", global_name="Test User", discriminator="0"
)


class TestListUsers:
    """Tests for UserAPIHandler.list_users()."""

    async def test_returns_users(self, fake_vclient):
        """Verify delegates to API and returns users."""
        # Given: the API returns users
        u1 = UserFactory.build(id="u-001", username="alice")
        u2 = UserFactory.build(id="u-002", username="bob")
        fake_vclient.set_response(Routes.USERS_LIST, items=[u1, u2])

        # When: listing users
        result = await user_api_handler.list_users()

        # Then: results returned
        assert len(result) == 2

    async def test_empty_list(self, fake_vclient):
        """Verify handles empty user list gracefully."""
        # Given: the API returns no users
        fake_vclient.set_response(Routes.USERS_LIST, items=[])

        # When: listing users
        result = await user_api_handler.list_users()

        # Then: empty list returned
        assert result == []


class TestGetUser:
    """Tests for UserAPIHandler.get_user()."""

    async def test_returns_user(self, fake_vclient):
        """Verify delegates to API and returns user."""
        # Given: the API returns a user
        user = UserFactory.build(id="u-001", username="alice")
        fake_vclient.set_response(Routes.USERS_GET, model=user)

        # When: getting a user
        result = await user_api_handler.get_user("u-001")

        # Then: correct user returned
        assert result.id == "u-001"
        assert result.username == "alice"


class TestCreateUser:
    """Tests for UserAPIHandler.create_user()."""

    async def test_creates_user(self, db, fake_vclient, mock_discord_member):
        """Verify API called and user synced to DB."""
        # Given: the API returns a created user
        user = UserFactory.build(
            id="u-001",
            username="newuser",
            email="new@example.com",
            role="PLAYER",
            discord_profile=_DISCORD_PROFILE,
        )
        fake_vclient.set_response(Routes.USERS_CREATE, model=user)

        # When: creating a user
        result = await user_api_handler.create_user(
            discord_user=mock_discord_member,
            requesting_user_api_id="admin-001",
            username="newuser",
            email="new@example.com",
            role="PLAYER",
        )

        # Then: user is synced to DB
        db_user = await DBUser.get_or_none(discord_user_id=mock_discord_member.id)
        assert db_user is not None
        assert db_user.api_user_id == "u-001"
        assert result.username == "newuser"

    async def test_db_sync_fields(self, db, fake_vclient, mock_discord_member):
        """Verify DBUser record created with correct fields."""
        # Given: the API returns a user with specific fields
        user = UserFactory.build(
            id="u-042",
            username="jane",
            email="jane@example.com",
            role="ADMIN",
            discord_profile=_DISCORD_PROFILE,
        )
        fake_vclient.set_response(Routes.USERS_CREATE, model=user)

        # When: creating the user
        await user_api_handler.create_user(
            discord_user=mock_discord_member,
            requesting_user_api_id="admin-001",
            username="jane",
            email="jane@example.com",
            role="ADMIN",
        )

        # Then: DBUser has all correct fields
        db_user = await DBUser.get(discord_user_id=mock_discord_member.id)
        assert db_user.api_user_id == "u-042"
        assert db_user.username == "jane"
        assert db_user.email == "jane@example.com"


class TestUpdateUser:
    """Tests for UserAPIHandler.update_user()."""

    async def test_updates_user(self, db, fake_vclient, mock_discord_member):
        """Verify API update called and user synced to DB."""
        # Given: the API returns an updated user
        user = UserFactory.build(
            id="u-001",
            username="updateduser",
            role="PLAYER",
            discord_profile=_DISCORD_PROFILE,
        )
        fake_vclient.set_response(Routes.USERS_UPDATE, model=user)

        # When: updating the user
        result = await user_api_handler.update_user(
            user_api_id="u-001",
            discord_user=mock_discord_member,
            requesting_user_api_id="admin-001",
            username="updateduser",
        )

        # Then: user is synced to DB
        db_user = await DBUser.get_or_none(discord_user_id=mock_discord_member.id)
        assert db_user is not None
        assert result.username == "updateduser"


class TestDeleteUser:
    """Tests for UserAPIHandler.delete_user()."""

    async def test_deletes_user(self, db, fake_vclient):
        """Verify API delete called and DB record removed."""
        # Given: a user exists in the DB
        await DBUser.create(
            discord_user_id=123456789,
            api_user_id="u-001",
            username="testuser",
            role="PLAYER",
        )

        # Given: the API accepts the delete
        fake_vclient.set_response(Routes.USERS_DELETE)

        # When: deleting the user
        await user_api_handler.delete_user("u-001", "admin-001")

        # Then: DB record is removed
        assert await DBUser.filter(api_user_id="u-001").count() == 0


class TestUpdateOrCreateUserValidation:
    """Tests for UserAPIHandler._update_or_create_user() edge cases."""

    async def test_no_discord_profile_raises(self, db):
        """Verify raises ValidationError when user has no discord_profile."""
        # Given: a user DTO with no discord profile
        user = UserFactory.build(id="u-001", discord_profile=None)

        # When/Then: raises ValidationError
        with pytest.raises(ValidationError, match="Discord profile"):
            await user_api_handler._update_or_create_user(user)
