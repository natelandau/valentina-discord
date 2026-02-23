"""Handler for user API events."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger
from vclient import users_service
from vclient.models import UserCreate, UserUpdate

from vbot.db.models import DBUser
from vbot.lib import exceptions
from vbot.utils import build_discord_profile

if TYPE_CHECKING:
    import discord
    from vclient.constants import UserRole
    from vclient.models import User

__all__ = ("user_api_handler",)


class UserAPIHandler:
    """Handler for user API events."""

    async def _update_or_create_user(self, user: User) -> DBUser:
        """Update or create a user in the database.

        Args:
            user (User): The user to update or create.

        Returns:
            DBUser: The user database object.

        Raises:
            exceptions.ValidationError: If the user does not have a Discord profile.
        """
        if not user.discord_profile:
            msg = "User does not have a Discord profile."
            raise exceptions.ValidationError(msg)

        db_user, created = await DBUser.update_or_create(
            discord_user_id=user.discord_profile.id,
            defaults={
                "api_user_id": user.id,
                "name": user.name,
                "email": user.email,
                "role": user.role,
            },
        )

        if created:
            logger.debug(
                "Create user in database.",
                user_id=user.id,
                user_name=user.name,
            )

        return db_user

    async def list_users(self) -> list[User]:
        """List all users from the API."""
        return await users_service().list_all()

    async def get_user(self, user_api_id: str) -> User:
        """Get the user from the API."""
        return await users_service().get(user_api_id)

    async def create_user(
        self,
        *,
        discord_user: discord.Member | discord.User,
        requesting_user_api_id: str,
        name: str,
        email: str,
        role: UserRole,
    ) -> User:
        """Create a new user in the API.

        Args:
            discord_user (discord.Member | discord.User): The Discord user to create.
            requesting_user_api_id (str): The API ID of the user requesting the creation.
            name (str): The name of the user to create.
            email (str): The email of the user to create.
            role (UserRole): The role of the user to create.

        Returns:
            User: The created user.
        """
        discord_profile = build_discord_profile(discord_user)

        user_dto = UserCreate(
            name=name,
            email=email,
            role=role,
            discord_profile=discord_profile,
            requesting_user_id=requesting_user_api_id,
        )

        user = await users_service().create(request=user_dto)

        await self._update_or_create_user(user)

        return user

    async def update_user(
        self,
        *,
        user_api_id: str,
        discord_user: discord.Member | discord.User,
        requesting_user_api_id: str,
        name: str | None = None,
        email: str | None = None,
        role: UserRole | None = None,
    ) -> User:
        """Update a user in the API.

        Args:
            user_api_id (str): The API ID of the user to update.
            discord_user (discord.Member | discord.User): The Discord user to update.
            requesting_user_api_id (str): The API ID of the user requesting the update.
            name (str | None): The name of the user to update.
            email (str | None): The email of the user to update.
            role (UserRole | None): The role of the user to update.

        Returns:
            User: The updated user.
        """
        discord_profile = build_discord_profile(discord_user)

        user_dto = UserUpdate(
            name=name,
            email=email,
            role=role or None,
            discord_profile=discord_profile,
            requesting_user_id=requesting_user_api_id,
        )

        user = await users_service().update(user_id=user_api_id, request=user_dto)

        await self._update_or_create_user(user)

        return user

    async def delete_user(self, user_api_id: str, requesting_user_api_id: str) -> None:
        """Delete a user in the API.

        Args:
            user_api_id (str): The API ID of the user to delete.
            requesting_user_api_id (str): The API ID of the user requesting the deletion.

        Returns:
            None
        """
        await users_service().delete(user_id=user_api_id, requesting_user_id=requesting_user_api_id)

        await DBUser.filter(api_user_id=user_api_id).delete()

        logger.debug(
            "Delete user from database and API.",
            user_id=user_api_id,
        )


user_api_handler = UserAPIHandler()
