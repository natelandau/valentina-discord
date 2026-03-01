"""Autocompletions for the admin cog."""

from __future__ import annotations

from typing import TYPE_CHECKING

from discord import OptionChoice
from vclient import users_service

from vbot.constants import MAX_OPTION_LIST_SIZE
from vbot.db.models import DBUser

if TYPE_CHECKING:
    from vbot.bot import ValentinaAutocompleteContext

__all__ = ("select_api_user_all", "select_api_user_unlinked")


async def select_api_user_all(ctx: ValentinaAutocompleteContext) -> list[OptionChoice]:
    """Generate a list of all users in the company from the API.

    This function fetches the users from the bot's user service,
    retrieves the argument from the context options,
    and filters the users based on the starting string of the user name.
    If the number of users reaches a maximum size, it stops appending more users.
    """
    try:
        users = await users_service().list_all()
    except ValueError:
        return [OptionChoice("No company found. Link a company first.", "")]

    if not users:
        return [OptionChoice("No users found in the company. Create one first.", "")]

    argument = ctx.options.get("user") or ""

    return [
        OptionChoice(user.username, str(user.id))
        for user in sorted(users, key=lambda x: x.username)
        if user.username.lower().startswith(argument.lower())
    ][:MAX_OPTION_LIST_SIZE]


async def select_api_user_unlinked(ctx: ValentinaAutocompleteContext) -> list[OptionChoice]:
    """Generate a list of all users in the company from the API that are not linked to a Discord user.

    This function fetches the users from the bot's user service,
    retrieves the argument from the context options,
    and filters the users based on the starting string of the user name.
    If the number of users reaches a maximum size, it stops appending more users.
    """
    try:
        users = await users_service().list_all()
    except ValueError:
        return [OptionChoice("No company found. Link a company first.", "")]

    all_db_users = await DBUser.all()
    unlinked_users = [
        user for user in users if user.id not in [db_user.api_user_id for db_user in all_db_users]
    ]

    if not unlinked_users:
        return [
            OptionChoice(
                "No users found in the company who are not already linked to a Discord user. Create one first.",
                "",
            )
        ]

    argument = ctx.options.get("user") or ""

    return [
        OptionChoice(user.username, str(user.id))
        for user in sorted(unlinked_users, key=lambda x: x.username)
        if user.username.lower().startswith(argument.lower())
    ][:MAX_OPTION_LIST_SIZE]
