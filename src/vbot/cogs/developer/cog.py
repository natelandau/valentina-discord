"""Developer cog."""

import discord
from discord.ext import commands
from loguru import logger
from vclient import system_service

from vbot.bot import Valentina, ValentinaContext
from vbot.constants import CHANNEL_PERMISSIONS
from vbot.db.models import Server
from vbot.lib.channel_mngr import ChannelManager
from vbot.views import present_embed
from vbot.workflows import confirm_action


class DeveloperCog(commands.Cog):
    """Campaign cog."""

    def __init__(self, bot: Valentina):
        self.bot = bot

    developer = discord.SlashCommandGroup(
        "developer",
        "Valentina developer commands. Beware, these can be destructive.",
        default_member_permissions=discord.Permissions(administrator=True),
    )
    guild = developer.create_subgroup(
        "guild",
        "Work with the current guild",
        default_member_permissions=discord.Permissions(administrator=True),
    )

    @guild.command()
    @commands.guild_only()
    @commands.is_owner()
    async def reset_discord_channels(self, ctx: ValentinaContext) -> None:
        """Reset the Discord channels for the current guild."""
        title = f"This is a destructive action and will delete all channels in the guild.\n\nReset the Discord channels for `{ctx.guild.name}`"
        is_confirmed, msg, confirmation_embed = await confirm_action(ctx, title=title, hidden=True)
        if not is_confirmed:
            return

        for channel in ctx.guild.channels:
            if channel.name == "general":
                continue
            logger.debug(f"Deleting channel {channel.name}")
            await channel.delete()

        channel_manager = ChannelManager(guild=ctx.guild)
        audit_log_channel = await channel_manager.channel_update_or_add(
            name="audit-log",
            topic="Valentina interaction audit reports",
            permissions=CHANNEL_PERMISSIONS["audit_log"],
        )
        error_log_channel = await channel_manager.channel_update_or_add(
            name="error-log",
            topic="Valentina error reports",
            permissions=CHANNEL_PERMISSIONS["error_log_channel"],
        )
        changelog_channel = await channel_manager.channel_update_or_add(
            name="changelog",
            topic="Valentina changelog",
            permissions=CHANNEL_PERMISSIONS["audit_log"],
        )
        storyteller_channel = await channel_manager.channel_update_or_add(
            name="storyteller",
            topic="Valentina storyteller channel",
            permissions=CHANNEL_PERMISSIONS["storyteller_channel"],
        )

        await Server.update_or_create(
            guild_id=ctx.guild.id,
            defaults={
                "name": ctx.guild.name,
                "audit_log_channel_id": audit_log_channel.id,
                "error_log_channel_id": error_log_channel.id,
                "changelog_channel_id": changelog_channel.id,
                "storyteller_channel_id": storyteller_channel.id,
            },
        )

        await msg.edit_original_response(embed=confirmation_embed, view=None)

    @developer.command()
    @commands.is_owner()
    async def api_status(self, ctx: ValentinaContext) -> None:
        """Get the status of the Valentina API."""
        status = await system_service().health()

        await present_embed(
            ctx,
            title="API Status",
            level="success",
            fields=[
                ("Database", status.database_status),
                ("Cache", status.cache_status),
                ("Version", status.version),
            ],
            ephemeral=False,
            inline_fields=True,
        )


def setup(bot: Valentina) -> None:
    """Register the cog with the bot.

    Initialize and add the cog to the Discord bot's extension system.
    This function is called automatically by the bot's extension loader.

    Args:
        bot (Valentina): The bot instance to register the cog with.
    """
    bot.add_cog(DeveloperCog(bot))
