"""Discord utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, assert_never

import discord
from loguru import logger
from vclient import books_service, campaigns_service, characters_service
from vclient.models import DiscordProfile

from vbot.constants import CampaignChannelName, ChannelPermission
from vbot.db.models import DBCampaign, DBCampaignBook, DBCharacter, DBUser
from vbot.lib import exceptions

if TYPE_CHECKING:
    from vclient.constants import UserRole

    from vbot.bot import Valentina, ValentinaAutocompleteContext, ValentinaContext

__all__ = (
    "assert_permissions",
    "build_discord_profile",
    "fetch_channel_object",
    "set_channel_perms",
)


@dataclass(eq=True)
class ChannelObjects:
    """Dataclass for Channel Objects."""

    campaign: DBCampaign | None
    book: DBCampaignBook | None
    character: DBCharacter | None
    is_storyteller_channel: bool

    def __bool__(self) -> bool:
        """Return True if any of the objects are present."""
        return any([self.campaign, self.book, self.character])


def build_discord_profile(member: discord.Member | discord.User) -> DiscordProfile:
    """Build a DiscordProfile DTO from a Discord member or user object.

    Args:
        member: The Discord member or user to extract profile data from.

    Returns:
        DiscordProfile: A populated DiscordProfile data transfer object.
    """
    return DiscordProfile(
        id=str(member.id),
        username=member.name,
        global_name=member.global_name,
        avatar_id=str(member.avatar.key) if member.avatar else None,
        avatar_url=member.avatar.url if member.avatar else None,
        discriminator=member.discriminator,
    )


async def assert_permissions(
    ctx: ValentinaContext,
    **permissions: bool,
) -> None:  # pragma: no cover
    """Check if the bot has the required permissions to run the command.

    Verify that the bot has the necessary permissions specified in the permissions argument.
    Raise an error if any required permissions are missing.

    Args:
        ctx (ValentinaContext): The context object containing the bot's permissions.
        **permissions (bool): Key-value pairs of permissions to check. Keys are permission
            names and values are the required states (True/False).

    Raises:
        BotMissingPermissionsError: If any required permissions are missing.
    """
    if missing := [
        perm for perm, value in permissions.items() if getattr(ctx.app_permissions, perm) != value
    ]:
        raise exceptions.BotMissingPermissionsError(missing)


async def get_discord_member_from_api_user_id(
    ctx: ValentinaContext,
    *,
    api_user_id: str,
) -> discord.Member | None:
    """Get the Discord member from the API user ID.

    Args:
        ctx (ValentinaContext): The context containing the guild.
        api_user_id (str): The API user ID.

    Returns:
        discord.Member | None: The Discord member or None if not found.
    """
    api_user = await DBUser.get_or_none(api_user_id=api_user_id)
    if not api_user:
        return None
    return discord.utils.get(ctx.guild.members, id=api_user.discord_user_id)


async def fetch_channel_object(
    ctx: ValentinaContext | ValentinaAutocompleteContext,
    *,
    raise_error: bool = True,
    need_book: bool = False,
    need_character: bool = False,
    need_campaign: bool = False,
    refresh_from_api: bool = False,
) -> ChannelObjects:  # pragma: no cover
    """Determine the channel type and fetch associated objects.

    Identify the channel type and fetch related campaign, book, and character objects. Raise errors if specified conditions are not met.

    Args:
        ctx (ValentinaContext): The context containing the channel object.
        raise_error (bool, optional): Whether to raise an error if no active objects are found. Defaults to True.
        need_book (bool, optional): Whether to raise an error if no book is found. Defaults to False.
        need_character (bool, optional): Whether to raise an error if no character is found. Defaults to False.
        need_campaign (bool, optional): Whether to raise an error if no campaign is found. Defaults to False.
        refresh_from_api (bool, optional): Whether to refresh the campaign and book from the API. Defaults to False.

    Returns:
        ChannelObjects: An object containing the campaign, book, character, and a flag for storyteller channel.

    Raises:
        errors.ChannelTypeError: If the required objects are not found based on the specified conditions.
    """
    user_api_id = await ctx.get_api_user_id()

    discord_channel = (
        ctx.interaction.channel if isinstance(ctx, discord.AutocompleteContext) else ctx.channel
    )

    db_campaign = None
    if discord_channel.category:  # type: ignore [union-attr]
        db_campaign = await DBCampaign.get_or_none(category_channel_id=discord_channel.category.id)  # type: ignore [union-attr]
        if db_campaign and refresh_from_api:
            campaign_dto = await campaigns_service(user_id=user_api_id).get(
                campaign_id=db_campaign.api_id
            )
            db_campaign, _ = await DBCampaign.update_or_create(
                api_id=campaign_dto.id,
                defaults={"name": campaign_dto.name},
            )

    if raise_error and need_campaign and not db_campaign:
        msg = "Rerun command in a channel associated with a campaign"
        raise exceptions.ChannelTypeError(msg)

    db_book = await DBCampaignBook.get_or_none(book_channel_id=discord_channel.id).prefetch_related(
        "campaign"
    )
    if db_book and refresh_from_api:
        book_dto = await books_service(
            user_id=user_api_id, campaign_id=db_book.campaign.api_id
        ).get(db_book.api_id)
        db_book, _ = await DBCampaignBook.update_or_create(
            api_id=book_dto.id,
            defaults={"name": book_dto.name, "number": book_dto.number, "campaign": db_campaign},
        )

    db_character = await DBCharacter.get_or_none(
        character_channel_id=discord_channel.id
    ).prefetch_related("campaign")
    if db_character and refresh_from_api:
        character_dto = await characters_service(
            user_id=user_api_id, campaign_id=db_campaign.api_id
        ).get(db_character.api_id)
        db_character, _ = await DBCharacter.update_or_create(
            api_id=character_dto.id,
            defaults={
                "name": character_dto.name,
                "campaign": db_campaign,
                "user_player_api_id": character_dto.user_player_id,
                "user_creator_api_id": character_dto.user_creator_id,
                "type": character_dto.type,
                "status": character_dto.status,
            },
        )

    if raise_error and need_character and not db_character:
        msg = "Rerun command in a character channel."
        raise exceptions.ChannelTypeError(msg)

    if raise_error and need_book and not db_book:
        msg = "Rerun command in a book channel"
        raise exceptions.ChannelTypeError(msg)

    if raise_error and not db_campaign and not db_book and not db_character:
        raise exceptions.ChannelTypeError

    is_storyteller_channel = (
        discord_channel and discord_channel.name == CampaignChannelName.STORYTELLER.value  # type: ignore [union-attr]
    )

    return ChannelObjects(
        campaign=db_campaign,
        book=db_book,
        character=db_character,
        is_storyteller_channel=is_storyteller_channel,  # type: ignore [arg-type]
    )


def set_channel_perms(
    requested_permission: ChannelPermission,
) -> discord.PermissionOverwrite:  # pragma: no cover
    """Create a Discord PermissionOverwrite object based on the requested permission level.

    This function maps a ChannelPermission enum to a set of Discord permissions,
    creating a PermissionOverwrite object with the appropriate settings.

    Args:
        requested_permission (ChannelPermission): The desired permission level for the channel.

    Returns:
        discord.PermissionOverwrite: A PermissionOverwrite object with the permissions set
        according to the requested permission level.
    """
    # Map each ChannelPermission to the properties that should be False
    permission_mapping: dict[ChannelPermission, dict[str, bool]] = {
        ChannelPermission.HIDDEN: {
            "add_reactions": False,
            "manage_messages": False,
            "read_messages": False,
            "send_messages": False,
            "view_channel": False,
            "read_message_history": False,
        },
        ChannelPermission.READ_ONLY: {
            "add_reactions": True,
            "manage_messages": False,
            "read_messages": True,
            "send_messages": False,
            "view_channel": True,
            "read_message_history": True,
            "use_slash_commands": False,
        },
        ChannelPermission.POST: {
            "add_reactions": True,
            "manage_messages": False,
            "read_messages": True,
            "send_messages": True,
            "view_channel": True,
            "read_message_history": True,
            "use_slash_commands": True,
        },
        ChannelPermission.MANAGE: {
            "add_reactions": True,
            "manage_messages": True,
            "read_messages": True,
            "send_messages": True,
            "view_channel": True,
            "read_message_history": True,
            "use_slash_commands": True,
        },
    }

    # Create a permission overwrite object
    perms = discord.PermissionOverwrite()
    # Update the permission overwrite object based on the enum
    for key, value in permission_mapping.get(requested_permission, {}).items():
        setattr(perms, key, value)

    return perms


async def set_user_role(  # noqa: C901, PLR0912
    bot: Valentina, *, guild: discord.Guild, member: discord.Member, role: UserRole
) -> None:
    """Set the role of a Discord user on this discord server.

    Args:
        bot (Valentina): The bot instance.
        guild (discord.Guild): The Discord guild.
        member (discord.Member): The Discord user to set the role of.
        role (UserRole): The role to set for the user.
    """
    admin_role = await bot.get_admin_role(guild)
    storyteller_role = await bot.get_storyteller_role(guild)
    player_role = await bot.get_player_role(guild)

    match role:
        case "PLAYER":
            if any(role.name in ("Storyteller", "@Storyteller") for role in member.roles):
                await member.remove_roles(storyteller_role)
            if any(role.name in ("Admin", "@Admin") for role in member.roles):
                await member.remove_roles(admin_role)

            if not any(role.name in ("Player", "@Player") for role in member.roles):
                logger.debug(f"DISCORD: Adding player role to {member.display_name}")
                await member.add_roles(player_role)

        case "STORYTELLER":
            if any(role.name in ("Player", "@Player") for role in member.roles):
                await member.remove_roles(player_role)
            if any(role.name in ("Admin", "@Admin") for role in member.roles):
                await member.remove_roles(admin_role)

            if not any(role.name in ("Storyteller", "@Storyteller") for role in member.roles):
                logger.debug(f"DISCORD: Adding storyteller role to {member.display_name}")
                await member.add_roles(storyteller_role)

        case "ADMIN":
            if any(role.name in ("Player", "@Player") for role in member.roles):
                await member.remove_roles(player_role)
            if any(role.name in ("Storyteller", "@Storyteller") for role in member.roles):
                await member.remove_roles(storyteller_role)

            if not any(role.name in ("Admin", "@Admin") for role in member.roles):
                logger.debug(f"DISCORD: Adding admin role to {member.display_name}")
                await member.add_roles(admin_role)
        case _:
            assert_never(role)
