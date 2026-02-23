"""Validation utilities."""

import discord

from vbot.db.models import DBUser
from vbot.lib import exceptions


async def get_valid_linked_db_user(discord_user: discord.Member | discord.User) -> DBUser:
    """Get the valid linked user from a Discord user.

    Args:
        discord_user (discord.Member): The Discord user to validate.

    Returns:
        DBUser: The API user if the user is linked to the API and not a bot.

    Raises:
        exceptions.UserNotLinkedError: If the user is a bot or not linked to a Valentina user.
    """
    user_name = (
        discord_user.display_name if isinstance(discord_user, discord.Member) else discord_user.name
    )
    if discord_user.bot:
        msg = f"The user `{user_name}` is a bot."
        raise exceptions.UserNotLinkedError(msg)

    api_user = await DBUser.get_or_none(discord_user_id=discord_user.id)
    if not api_user or not api_user.api_user_id:
        msg = f"The user `{user_name}` is not linked to a Valentina user."
        raise exceptions.UserNotLinkedError(msg)

    return api_user


def empty_string_to_none(value: str) -> str | None:
    """Convert an empty string to None.

    Args:
        value (str): The string to convert.

    Returns:
        str | None: The converted string or None if the string is empty.
    """
    if not value:
        return None

    if value.strip() == "":
        return None
    return value
