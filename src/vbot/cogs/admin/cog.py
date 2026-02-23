"""Administrative commands for managing Valentina integration with Discord.

This module provides commands for administrators to link Discord servers and users
to Valentina companies and users, as well as create new companies and users in the
Valentina API. All commands require administrator permissions in Discord.
"""

import re
from typing import TYPE_CHECKING, Annotated, cast

import discord
import inflect
from discord.commands import Option
from discord.ext import commands
from loguru import logger

from vbot.bot import Valentina, ValentinaContext
from vbot.db.models import DBCampaign, DBUser
from vbot.handlers import user_api_handler
from vbot.lib import exceptions
from vbot.lib.channel_mngr import ChannelManager
from vbot.utils import assert_permissions, set_user_role, truncate_string
from vbot.views import UserModal, present_embed
from vbot.workflows import confirm_action

from . import autocomplete
from .lib import resync_all_data

if TYPE_CHECKING:
    from vclient.constants import UserRole

p = inflect.engine()


class AdminCog(commands.Cog):
    """Provide administrative commands for managing Valentina integration.

    This cog contains commands for linking Discord servers and users to Valentina,
    creating new companies and users, and managing these relationships. All commands
    require administrator permissions in Discord.
    """

    def __init__(self, bot: Valentina):
        self.bot = bot

    admin = discord.SlashCommandGroup(
        "admin",
        "Administer Valentina",
        default_member_permissions=discord.Permissions(administrator=True),
    )
    campaign = admin.create_subgroup(name="campaign", description="Manage campaigns.")
    channel = admin.create_subgroup(name="channel", description="Manage channels.")
    user = admin.create_subgroup(name="user", description="Manage users.")
    valentina = admin.create_subgroup(
        name="valentina", description="Interact with the central Valentina API."
    )

    ### VALENTINA API MANAGEMENT #######################################################
    @valentina.command(name="resync", description="Resync all data from the Valentina API.")
    @commands.has_permissions(administrator=True)
    async def resync_api_data(
        self,
        ctx: ValentinaContext,
        hidden: Annotated[
            bool,
            Option(
                name="hidden",
                description="Make the response visible only to you (default true).",
                required=False,
                default=True,
            ),
        ],
    ) -> None:
        """Resync all data from the Valentina API."""
        title = "Resync all data from the Valentina API"
        description = "This may take a while as all data is pulled and channels are rebuilt. Some data loss in channels may occur."
        is_confirmed, msg, confirmation_embed = await confirm_action(
            ctx, title=title, description=description, hidden=hidden
        )
        if not is_confirmed:
            return

        api_user_id = await ctx.get_api_user_id()
        messages = await resync_all_data(user_api_id=api_user_id, guild=ctx.guild)

        confirmation_embed.description = "All data has been resynced from the Valentina API.\n"
        confirmation_embed.description += "\n - ".join(messages)
        try:
            await msg.edit_original_response(embed=confirmation_embed, view=None)
        except discord.NotFound:
            logger.warning(
                "Message not found. The user may have deleted it.",
                message_id=msg.id,
            )

    ### USER MANAGEMENT #######################################################

    @user.command(name="link-self", description="Link an administrator to themselves.")
    @commands.has_permissions(administrator=True)
    async def user_link_self(
        self,
        ctx: ValentinaContext,
        api_user_id: Annotated[
            str,
            Option(
                autocomplete=autocomplete.select_api_user_all,
                name="valentina_user",
                description="The Valentina user to link yourself to",
                required=True,
            ),
        ],
        hidden: Annotated[
            bool,
            Option(
                name="hidden",
                description="Make the response visible only to you (default true).",
                required=False,
                default=True,
            ),
        ],
    ) -> None:
        """Link an administrator to themselves."""
        if not api_user_id:
            m = "No users found. Create one first."
            raise exceptions.UserNotLinkedError(m)

        api_user = await user_api_handler.get_user(api_user_id)

        title = f"Link {ctx.author.name} (you) to {api_user.name}"
        description = f"This will allow {ctx.author.name} to administer this server via Valentina.\n\nAre you sure you want to link `{ctx.author.name}` to `{api_user.name}`?"
        is_confirmed, msg, confirmation_embed = await confirm_action(
            ctx, title=title, description=description, hidden=hidden
        )
        if not is_confirmed:
            return

        await user_api_handler.update_user(
            user_api_id=api_user_id,
            discord_user=ctx.author,
            requesting_user_api_id=api_user_id,
        )

        await set_user_role(
            bot=ctx.bot,
            guild=ctx.guild,
            member=ctx.author,  # type: ignore [arg-type]
            role=api_user.role,
        )

        confirmation_embed.description = f"{ctx.author.name} has been linked to {api_user.name}."
        await msg.edit_original_response(embed=confirmation_embed, view=None)

    @user.command(name="link", description="Link a Discord user to an existing Valentina user.")
    async def user_link(
        self,
        ctx: ValentinaContext,
        discord_user: Annotated[
            discord.Member,
            Option(
                name="discord_user",
                description="The Discord user to link.",
                required=True,
            ),
        ],
        api_user_id: Annotated[
            str,
            Option(
                autocomplete=autocomplete.select_api_user_unlinked,
                name="valentina_user",
                description="The Valentina user to link to",
                required=True,
            ),
        ],
        hidden: Annotated[
            bool,
            Option(
                name="hidden",
                description="Make the response visible only to you (default true).",
                required=False,
                default=True,
            ),
        ],
    ) -> None:
        """Associate a Discord user with a Valentina user account.

        Link a Discord user to a specific Valentina user account and assign them a role.
        Updates the user's role in the Valentina API if it differs from the selected role.
        Presents a confirmation dialog before completing the link operation.

        Args:
            ctx (ValentinaContext): The Discord command context.
            discord_user (discord.Member): The Discord user to link.
            api_user_id (str): ID of the Valentina user to link to, selected via autocomplete.
            hidden (bool): Make the response visible only to you (default true).
        """
        if not api_user_id:
            m = "No users found. Create one first."
            raise exceptions.UserNotLinkedError(m)

        new_api_user = await user_api_handler.get_user(api_user_id)
        requesting_user_api_id = await ctx.get_api_user_id()

        title = f"Link {discord_user.name} user to {new_api_user.name}"
        description = f"This will allow {discord_user.name} to use commands in this server.\n\nAre you sure you want to link {discord_user.name} to {new_api_user.name}?"
        is_confirmed, msg, confirmation_embed = await confirm_action(
            ctx, title=title, description=description, hidden=hidden
        )
        if not is_confirmed:
            return

        await user_api_handler.update_user(
            user_api_id=new_api_user.id,
            discord_user=discord_user,
            requesting_user_api_id=requesting_user_api_id,
        )

        await set_user_role(
            bot=ctx.bot, guild=ctx.guild, member=discord_user, role=new_api_user.role
        )

        confirmation_embed.description = (
            f"{discord_user.name} has been linked to {new_api_user.name}."
        )
        await msg.edit_original_response(embed=confirmation_embed, view=None)

    @user.command(name="unlink", description="Unlink a Discord user from a Valentina user.")
    async def user_unlink(
        self,
        ctx: ValentinaContext,
        discord_user: discord.Member,
        hidden: Annotated[
            bool,
            Option(
                name="hidden",
                description="Make the response visible only to you (default true).",
                required=False,
                default=True,
            ),
        ],
    ) -> None:
        """Remove the association between a Discord user and their Valentina account.

        Delete the link between a Discord user and any associated Valentina user account.
        Presents a confirmation dialog before completing the unlink operation.

        Args:
            ctx (ValentinaContext): The Discord command context.
            discord_user (discord.Member): The Discord user to unlink from Valentina.
            hidden (bool): Make the response visible only to you (default true).
        """
        title = f"Unlink {discord_user.name} user from Valentina"
        description = f"This will remove the link between {discord_user.name} and Valentina. Are you sure you want to unlink {discord_user.name}?"
        is_confirmed, msg, confirmation_embed = await confirm_action(
            ctx, title=title, description=description, hidden=hidden
        )
        if not is_confirmed:
            return

        await DBUser.filter(discord_user_id=discord_user.id).delete()

        if any(role.name in ("Storyteller", "@Storyteller") for role in discord_user.roles):
            player_role = await ctx.bot.get_player_role(ctx.guild)
            storyteller_role = await ctx.bot.get_storyteller_role(ctx.guild)

            await discord_user.remove_roles(storyteller_role)
            await discord_user.add_roles(player_role)

        confirmation_embed.description = f"{discord_user.name} has been unlinked from Valentina."
        await msg.edit_original_response(embed=confirmation_embed, view=None)

    @user.command(
        name="create", description="Create a new Valentina User linked to a Discord user."
    )
    async def user_create(
        self,
        ctx: ValentinaContext,
        discord_user: Annotated[
            discord.Member,
            Option(
                name="discord_user",
                description="The Discord user to link to this new user.",
                required=True,
            ),
        ],
        role: Annotated[
            str,
            Option(
                name="role",
                description="The role to assign to the user.",
                required=True,
                choices=["PLAYER", "ADMIN", "STORYTELLER"],
            ),
        ],
        hidden: Annotated[
            bool,
            Option(
                name="hidden",
                description="Make the response visible only to you (default true).",
                required=False,
            ),
        ],
    ) -> None:
        """Create a new Valentina user and link it to a Discord user.

        Display a modal dialog for entering user details, create the user in the
        Valentina API, and automatically link it to the specified Discord user with
        the assigned role.

        Args:
            ctx (ValentinaContext): The Discord command context.
            discord_user (discord.Member): The Discord user to link to the new Valentina user.
            role (str): Role to assign to the user, selected via autocomplete.
            hidden (bool): Make the response visible only to you (default true).
        """
        requesting_user_api_id = await ctx.get_api_user_id()

        modal = UserModal(title=truncate_string("Create new User", 45))
        await ctx.send_modal(modal)
        await modal.wait()
        if not modal.confirmed:
            return

        name = re.sub(r"[^-_a-zA-Z0-9\s]", "", modal.name.strip()).title()
        email = modal.email.strip()

        await user_api_handler.create_user(
            discord_user=discord_user,
            requesting_user_api_id=requesting_user_api_id,
            name=name,
            email=email,
            role=cast("UserRole", role),
        )

        await set_user_role(
            bot=ctx.bot, guild=ctx.guild, member=discord_user, role=cast("UserRole", role)
        )

        await present_embed(
            ctx,
            title=f"Create User: `{name}`",
            level="success",
            description="User created successfully and linked to this Discord server.",
            ephemeral=hidden,
            inline_fields=True,
        )

    @user.command(name="permissions", description="Manage user permissions.")
    async def user_permissions(
        self,
        ctx: ValentinaContext,
        discord_user: discord.Member,
        role: Annotated[
            str,
            Option(
                name="role",
                description="The role to assign to the user.",
                required=True,
                choices=["PLAYER", "ADMIN", "STORYTELLER"],
            ),
        ],
        hidden: Annotated[
            bool,
            Option(
                name="hidden",
                description="Make the response visible only to you (default true).",
                required=False,
                default=True,
            ),
        ],
    ) -> None:
        """Manage user permissions."""
        requesting_user_api_id = await ctx.get_api_user_id()

        title = f"Set {discord_user.name}'s role to {role}"
        description = f"This will set {discord_user.name}'s role to {role}."
        is_confirmed, msg, confirmation_embed = await confirm_action(
            ctx, title=title, description=description, hidden=hidden
        )
        if not is_confirmed:
            return

        db_user = await DBUser.get_or_none(discord_user_id=discord_user.id)
        if not db_user:
            m = f"User {discord_user.name} not found in database. Please link this user to a Valentina user."
            raise exceptions.UserNotLinkedError(m)

        await user_api_handler.update_user(
            user_api_id=db_user.api_user_id,
            discord_user=discord_user,
            requesting_user_api_id=requesting_user_api_id,
            role=cast("UserRole", role),
        )

        await set_user_role(
            bot=ctx.bot, guild=ctx.guild, member=discord_user, role=cast("UserRole", role)
        )
        confirmation_embed.description = f"{discord_user.name}'s role has been set to {role}."
        await msg.edit_original_response(embed=confirmation_embed, view=None)

    ### CAMPAIGN MANAGEMENT #######################################################

    @discord.guild_only()
    @commands.has_permissions(administrator=True)
    @admin.command(
        name="delete_all_channels",
        description="Delete all campaign channels from Discord",
    )
    async def delete_champaign_channels(
        self,
        ctx: ValentinaContext,
        hidden: Annotated[
            bool,
            Option(
                name="hidden",
                description="Make the response visible only to you (default true).",
                required=False,
                default=True,
            ),
        ],
    ) -> None:
        """Delete all campaign channels from Discord."""
        title = f"Delete all campaign channels from `{ctx.guild.name}`"
        is_confirmed, interaction, confirmation_embed = await confirm_action(
            ctx, title=title, hidden=hidden
        )
        if not is_confirmed:
            return

        channel_manager = ChannelManager(guild=ctx.guild)
        for campaign in await DBCampaign.all():
            await channel_manager.delete_campaign_channels(campaign)

        await interaction.edit_original_response(embed=confirmation_embed, view=None)

    ### CHANNEL ADMINISTRATION COMMANDS ################################################################
    @channel.command(name="slowmode", description="Set slowmode for the current channel")
    @discord.guild_only()
    @commands.has_permissions(administrator=True)
    async def slowmode(
        self,
        ctx: ValentinaContext,
        seconds: Annotated[
            int,
            Option(
                name="seconds",
                description="The slowmode cooldown in seconds, 0 to disable slowmode",
                required=True,
            ),
        ],
        hidden: Annotated[
            bool,
            Option(
                name="hidden",
                description="Make the response visible only to you (default true).",
                required=False,
                default=True,
            ),
        ],
    ) -> None:
        """Set slowmode for the current channel."""
        if not isinstance(ctx.channel, discord.TextChannel):
            msg = "Slowmode can only be set in text channels."
            raise commands.BadArgument(msg)

        await assert_permissions(ctx, manage_channels=True)

        if not 21600 >= seconds >= 0:  # noqa: PLR2004
            await present_embed(
                ctx,
                title="Error setting slowmode",
                description="Slowmode should be between `21600` and `0` seconds",
                level="error",
                ephemeral=hidden,
            )
            return

        # Confirm the action
        title = f"Set slowmode to {seconds} seconds"
        is_confirmed, interaction, confirmation_embed = await confirm_action(
            ctx, title=title, hidden=hidden
        )
        if not is_confirmed:
            return

        await ctx.channel.edit(slowmode_delay=seconds)

        await interaction.edit_original_response(embed=confirmation_embed, view=None)

    @channel.command()
    @discord.guild_only()
    @commands.has_permissions(administrator=True)
    async def lock(
        self,
        ctx: ValentinaContext,
        *,
        reason: Annotated[
            str,
            Option(
                name="reason",
                description="The reason for locking this channel",
                required=True,
            ),
        ],
        hidden: Annotated[
            bool,
            Option(
                name="hidden",
                description="Make the response visible only to you (default true).",
                required=False,
                default=True,
            ),
        ],
    ) -> None:
        """Disable the `Send Message` permission for the default role."""
        await assert_permissions(ctx, manage_roles=True)

        if not isinstance(ctx.channel, discord.TextChannel):
            msg = "Only text channels can be locked"
            raise commands.BadArgument(msg)

        if ctx.channel.overwrites_for(ctx.guild.default_role).send_messages is False:
            await ctx.respond("This channel is already locked.", ephemeral=True)
            return

        # Confirm the action
        title = "Lock this channel"
        is_confirmed, interaction, confirmation_embed = await confirm_action(
            ctx, title=title, description=reason, hidden=hidden
        )
        if not is_confirmed:
            return

        await ctx.channel.edit(
            overwrites={ctx.guild.default_role: discord.PermissionOverwrite(send_messages=False)},
            reason=f"{ctx.author} ({ctx.author.id}): {reason}",
        )

        await interaction.edit_original_response(embed=confirmation_embed, view=None)

    @channel.command()
    @discord.guild_only()
    @commands.has_permissions(administrator=True)
    async def unlock(
        self,
        ctx: ValentinaContext,
        *,
        reason: Annotated[
            str,
            Option(
                name="reason",
                description="The reason for unlocking this channel",
                required=True,
            ),
        ],
        hidden: Annotated[
            bool,
            Option(
                name="hidden",
                description="Make the response visible only to you (default true).",
                required=False,
                default=True,
            ),
        ],
    ) -> None:
        """Set the `Send Message` permission to the default state for the default role."""
        await assert_permissions(ctx, manage_roles=True)
        if not isinstance(ctx.channel, discord.TextChannel):
            msg = "Only text channels can be locked or unlocked"
            raise commands.BadArgument(msg)

        if ctx.channel.overwrites_for(ctx.guild.default_role).send_messages is not False:
            await ctx.respond("This channel isn't locked.", ephemeral=True)
            return

        # Confirm the action
        title = "Unlock this channel"
        is_confirmed, interaction, confirmation_embed = await confirm_action(
            ctx, title=title, description=reason, hidden=hidden
        )
        if not is_confirmed:
            return

        await ctx.channel.edit(
            overwrites={ctx.guild.default_role: discord.PermissionOverwrite(send_messages=None)},
            reason=f"{ctx.author} ({ctx.author.id}): {reason}",
        )
        await interaction.edit_original_response(embed=confirmation_embed, view=None)

    @channel.command()
    @commands.has_permissions(administrator=True)
    @discord.option(
        "limit",
        description="The amount of messages to delete",
        min_value=1,
        max_value=50,
    )
    async def purge_old_messages(
        self,
        ctx: ValentinaContext,
        limit: int,
        reason: Annotated[
            str,
            Option(
                name="reason",
                description="The reason for purging messages.",
                required=True,
            ),
        ],
    ) -> None:
        """Delete messages from this channel."""
        await assert_permissions(ctx, read_message_history=True, manage_messages=True)

        if purge := getattr(ctx.channel, "purge", None):
            count = len(await purge(limit=limit, reason=reason))
            await present_embed(
                ctx,
                title=f"Purged `{count}` {p.plural_noun('message', count)} from this channel",
                level="warning",
                ephemeral=True,
            )
            return

        await ctx.respond("This channel cannot be purged", ephemeral=True)
        return

    @channel.command()
    @commands.has_permissions(administrator=True)
    @discord.option(
        "member",
        description="The member whose messages will be deleted.",
    )
    @discord.option(
        "limit",
        description="The amount of messages to search.",
        min_value=1,
        max_value=100,
    )
    async def purge_by_member(
        self,
        ctx: ValentinaContext,
        member: discord.Member,
        limit: int,
        *,
        reason: Annotated[
            str,
            Option(
                name="reason",
                description="The reason for purging messages",
                required=True,
            ),
        ],
    ) -> None:
        """Purge a member's messages from this channel."""
        await assert_permissions(ctx, read_message_history=True, manage_messages=True)

        if purge := getattr(ctx.channel, "purge", None):
            count = len(
                await purge(limit=limit, reason=reason, check=lambda m: m.author.id == member.id),
            )
            await present_embed(
                ctx,
                title=f"Purged `{count}` {p.plural_noun('message', count)} from `{member.display_name}` in this channel",
                level="warning",
                ephemeral=True,
            )
            return

        await ctx.respond("This channel cannot be purged", ephemeral=True)
        return

    @channel.command()
    @commands.has_permissions(administrator=True)
    @discord.option(
        "limit",
        description="The amount of messages to search.",
        min_value=1,
        max_value=100,
    )
    async def purge_bot_messages(
        self,
        ctx: ValentinaContext,
        limit: int,
        *,
        reason: Annotated[
            str,
            Option(
                name="reason",
                description="The reason for purging messages",
                required=True,
            ),
        ],
    ) -> None:
        """Purge bot messages from this channel."""
        await assert_permissions(ctx, read_message_history=True, manage_messages=True)

        if purge := getattr(ctx.channel, "purge", None):
            count = len(await purge(limit=limit, reason=reason, check=lambda m: m.author.bot))
            await present_embed(
                ctx,
                title=f"Purged `{count}` bot {p.plural_noun('message', count)} in this channel",
                level="warning",
                ephemeral=True,
            )
            return

        await ctx.respond("This channel cannot be purged", ephemeral=True)
        return

    @channel.command()
    @commands.has_permissions(administrator=True)
    @discord.option(
        "phrase",
        description="The phrase to delete messages containing it.",
    )
    @discord.option(
        "limit",
        description="The amount of messages to search.",
        min_value=1,
        max_value=100,
    )
    async def purge_containing(
        self,
        ctx: ValentinaContext,
        phrase: str,
        limit: int,
        *,
        reason: Annotated[
            str,
            Option(
                name="reason",
                description="The reason for purging messages",
                required=True,
            ),
        ],
    ) -> None:
        """Purge messages containing a specific phrase from this channel."""
        await assert_permissions(ctx, read_message_history=True, manage_messages=True)

        if purge := getattr(ctx.channel, "purge", None):
            count = len(
                await purge(limit=limit, reason=reason, check=lambda m: phrase in m.content),
            )
            await present_embed(
                ctx,
                title=f"Purged `{count}` {p.plural_noun('message', count)} containing `{phrase}` in this channel",
                level="warning",
                ephemeral=True,
            )
            return

        await ctx.respond("This channel cannot be purged", ephemeral=True)
        return


def setup(bot: Valentina) -> None:
    """Register the AdminCog with the bot.

    Initialize and add the AdminCog to the Discord bot's extension system.
    This function is called automatically by the bot's extension loader.

    Args:
        bot (Valentina): The bot instance to register the cog with.
    """
    bot.add_cog(AdminCog(bot))
