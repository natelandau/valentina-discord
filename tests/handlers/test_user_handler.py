"""Tests for the user API handler."""

from __future__ import annotations

import pytest

from tests.factories import make_user
from vbot.db.models import DBUser
from vbot.handlers.user import user_api_handler
from vbot.lib.exceptions import ValidationError

pytestmark = pytest.mark.anyio


class TestListUsers:
    """Tests for UserAPIHandler.list_users()."""

    async def test_delegates_to_api(self, mock_users_service):
        """Verify delegates to users_service().list_all()."""
        # Given: the API returns users
        users = [make_user(id="u-001"), make_user(id="u-002")]
        mock_users_service._service.list_all.return_value = users

        # When: listing users
        result = await user_api_handler.list_users()

        # Then: API was called and results returned
        mock_users_service.assert_called_once_with()
        mock_users_service._service.list_all.assert_awaited_once()
        assert len(result) == 2


class TestGetUser:
    """Tests for UserAPIHandler.get_user()."""

    async def test_delegates_to_api(self, mock_users_service):
        """Verify delegates to users_service().get()."""
        # Given: the API returns a user
        user = make_user(id="u-001")
        mock_users_service._service.get.return_value = user

        # When: getting a user
        result = await user_api_handler.get_user("u-001")

        # Then: API was called correctly
        mock_users_service._service.get.assert_awaited_once_with("u-001")
        assert result.id == "u-001"


class TestCreateUser:
    """Tests for UserAPIHandler.create_user()."""

    async def test_creates_user(self, db, mock_users_service, mock_discord_member):
        """Verify DiscordProfile built, API called, and DB synced."""
        # Given: the API returns a created user
        user = make_user(id="u-001", username="newuser", email="new@example.com")
        mock_users_service._service.create.return_value = user

        # When: creating a user
        result = await user_api_handler.create_user(
            discord_user=mock_discord_member,
            requesting_user_api_id="admin-001",
            username="newuser",
            email="new@example.com",
            role="PLAYER",
        )

        # Then: API was called with a UserCreate DTO
        mock_users_service._service.create.assert_awaited_once()
        call_kwargs = mock_users_service._service.create.call_args[1]
        request = call_kwargs["request"]
        assert request.username == "newuser"
        assert request.email == "new@example.com"
        assert request.role == "PLAYER"
        assert request.requesting_user_id == "admin-001"

        # Then: DiscordProfile was built from discord_user attributes
        assert request.discord_profile.id == str(mock_discord_member.id)
        assert request.discord_profile.username == mock_discord_member.name

        # Then: user is synced to DB
        db_user = await DBUser.get_or_none(discord_user_id=mock_discord_member.id)
        assert db_user is not None
        assert db_user.api_user_id == "u-001"
        assert result.username == "newuser"

    async def test_db_sync_fields(self, db, mock_users_service, mock_discord_member):
        """Verify DBUser record created with correct fields."""
        # Given: the API returns a user with specific fields
        user = make_user(id="u-042", username="jane", email="jane@example.com", role="ADMIN")
        mock_users_service._service.create.return_value = user

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

    async def test_updates_user(self, db, mock_users_service, mock_discord_member):
        """Verify UserUpdate DTO constructed and API called."""
        # Given: the API returns an updated user
        user = make_user(id="u-001", username="updateduser")
        mock_users_service._service.update.return_value = user

        # When: updating the user
        result = await user_api_handler.update_user(
            user_api_id="u-001",
            discord_user=mock_discord_member,
            requesting_user_api_id="admin-001",
            username="updateduser",
        )

        # Then: API was called with correct args
        mock_users_service._service.update.assert_awaited_once()
        call_kwargs = mock_users_service._service.update.call_args[1]
        assert call_kwargs["user_id"] == "u-001"
        request = call_kwargs["request"]
        assert request.username == "updateduser"
        assert request.requesting_user_id == "admin-001"

        # Then: user is synced to DB
        db_user = await DBUser.get_or_none(discord_user_id=mock_discord_member.id)
        assert db_user is not None
        assert result.username == "updateduser"


class TestDeleteUser:
    """Tests for UserAPIHandler.delete_user()."""

    async def test_deletes_user(self, db, mock_users_service):
        """Verify API delete called with both args and DB record removed."""
        # Given: a user exists in the DB
        await DBUser.create(
            discord_user_id=123456789,
            api_user_id="u-001",
            username="testuser",
            role="PLAYER",
        )

        # When: deleting the user
        await user_api_handler.delete_user("u-001", "admin-001")

        # Then: API was called with both user_id and requesting_user_id
        mock_users_service._service.delete.assert_awaited_once_with(
            user_id="u-001", requesting_user_id="admin-001"
        )

        # Then: DB record is removed
        assert await DBUser.filter(api_user_id="u-001").count() == 0


class TestUpdateOrCreateUserValidation:
    """Tests for UserAPIHandler._update_or_create_user() edge cases."""

    async def test_no_discord_profile_raises(self, db, mock_users_service):
        """Verify raises ValidationError when user has no discord_profile."""
        # Given: a user DTO with no discord profile
        user = make_user(id="u-001", discord_profile=None)

        # When/Then: raises ValidationError
        with pytest.raises(ValidationError, match="Discord profile"):
            await user_api_handler._update_or_create_user(user)
