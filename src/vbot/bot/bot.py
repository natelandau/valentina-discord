"""The main file for the Valentina bot."""

import asyncio
from datetime import UTC, datetime
from typing import Any

import discord
from discord.ext import commands, tasks
from loguru import logger

from vbot.config.base import settings
from vbot.constants import COGS_PATH
from vbot.db.models import DBUser, Server
from vbot.utils import set_user_role

from .context import ValentinaAutocompleteContext, ValentinaContext

logger.info("Valentina bot initialized")


class Valentina(commands.Bot):
    """Extend the discord.Bot class to create a custom bot implementation.

    Enhance the base discord.Bot with additional functionality
    specific to the Valentina bot. Include custom attributes, methods,
    and event handlers to manage bot state, load cogs, initialize the database,
    and handle server connections.

    Args:
        version (str): The version of the bot.
    """

    def __init__(
        self,
        version: str,
        *args: Any,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self.connected = False
        self.welcomed = False
        self.version = version
        self.owner_channels = [int(x) for x in settings.discord.owner_channels]
        self.sync_user_roles.start()

        cogs_to_load = [
            path.relative_to(COGS_PATH).as_posix().replace("/", ".").rstrip(".py")
            for path in COGS_PATH.glob("**/cog.py")
            if path.is_file()
        ]
        for cog in cogs_to_load:
            logger.debug(f"COGS: Loading - {cog}")
            self.load_extension("vbot.cogs." + cog)
            logger.info(f"COGS: Loaded - {cog}")

    async def _provision_guilds(self) -> None:
        """Provision the guilds for the bot."""
        for guild in self.guilds:
            logger.debug(f"DATABASE: Update server `{guild.name}`")
            await Server.update_or_create(guild_id=guild.id, defaults={"name": guild.name})

            # These methods create the roles if they don't exist.
            await self.get_admin_role(guild)
            await self.get_storyteller_role(guild)
            await self.get_player_role(guild)

            for member in guild.members:
                if not member.bot:
                    _, updated = await DBUser.update_or_create(
                        discord_user_id=member.id,
                        defaults={"name": member.display_name, "role": "PLAYER"},
                    )
                    if updated:
                        logger.debug(f"DATABASE: Updated user `{member.display_name}`")

    @staticmethod
    async def get_admin_role(guild: discord.Guild) -> discord.Role:  # pragma: no cover
        """Create or update the Admin role in a Discord guild."""
        admin = discord.utils.get(guild.roles, name="Admin")
        if not admin:
            admin = await guild.create_role(
                name="Admin",
                color=discord.Color.dark_red(),
                mentionable=True,
                hoist=True,
            )
            logger.info(f"CONNECT: {admin.name} role created/updated on {guild.name}")

        perms = discord.Permissions()
        perms.update(
            administrator=True,
        )
        await admin.edit(reason=None, permissions=perms)

        return admin

    @staticmethod
    async def get_storyteller_role(
        guild: discord.Guild,
    ) -> discord.Role:  # pragma: no cover
        """Create or update the storyteller role for the guild.

        Create a "Storyteller" role if it doesn't exist, or update its permissions if it does.
        The role is given specific permissions suitable for a storyteller in a role-playing game context.

        Args:
            guild (discord.Guild): The Discord guild to create or update the role in.

        Returns:
            discord.Role: The created or updated "Storyteller" role.
        """
        storyteller = discord.utils.get(guild.roles, name="Storyteller")

        if not storyteller:
            storyteller = await guild.create_role(
                name="Storyteller",
                color=discord.Color.dark_teal(),
                mentionable=True,
                hoist=True,
            )
            logger.info(f"CONNECT: {storyteller.name} role created/updated on {guild.name}")

        perms = discord.Permissions()
        perms.update(
            add_reactions=True,
            attach_files=True,
            can_create_instant_invite=True,
            change_nickname=True,
            connect=True,
            create_private_threads=True,
            create_public_threads=True,
            embed_links=True,
            external_emojis=True,
            external_stickers=True,
            manage_messages=True,
            manage_threads=True,
            mention_everyone=True,
            read_message_history=True,
            read_messages=True,
            send_messages_in_threads=True,
            send_messages=True,
            send_tts_messages=True,
            speak=True,
            stream=True,
            use_application_commands=True,
            use_external_emojis=True,
            use_external_stickers=True,
            use_slash_commands=True,
            use_voice_activation=True,
            view_channel=True,
        )
        await storyteller.edit(reason=None, permissions=perms)

        return storyteller

    @staticmethod
    async def get_player_role(guild: discord.Guild) -> discord.Role:  # pragma: no cover
        """Create or update the Player role in a Discord guild.

        This function creates a new Player role if it doesn't exist, or updates an existing one.
        The role is set with specific permissions suitable for regular players in the game.

        Args:
            guild (discord.Guild): The Discord guild where the role should be created or updated.

        Returns:
            discord.Role: The created or updated Player role.
        """
        player = discord.utils.get(guild.roles, name="Player", mentionable=True, hoist=True)

        if not player:
            player = await guild.create_role(
                name="Player",
                color=discord.Color.dark_blue(),
                mentionable=True,
                hoist=True,
            )
            logger.info(f"CONNECT: {player.name} role created/updated on {guild.name}")

        perms = discord.Permissions()
        perms.update(
            add_reactions=True,
            attach_files=True,
            can_create_instant_invite=True,
            change_nickname=True,
            connect=True,
            create_private_threads=True,
            create_public_threads=True,
            embed_links=True,
            external_emojis=True,
            external_stickers=True,
            mention_everyone=True,
            read_message_history=True,
            read_messages=True,
            send_messages_in_threads=True,
            send_messages=True,
            send_tts_messages=True,
            speak=True,
            stream=True,
            use_application_commands=True,
            use_external_emojis=True,
            use_external_stickers=True,
            use_slash_commands=True,
            use_voice_activation=True,
            view_channel=True,
        )
        await player.edit(reason=None, permissions=perms)

        return player

    async def on_connect(self) -> None:
        """Perform early setup tasks when the bot connects to Discord.

        Initialize the MongoDB database connection, retrying if necessary.
        Log connection details and bot information upon successful connection.
        Synchronize commands with Discord.
        """
        # Connect to discord
        if not self.connected:
            logger.info(f"Logged in as {self.user.name} ({self.user.id})")
            logger.info(
                f"CONNECT: Playing on {len(self.guilds)} servers",
            )
            logger.info(f"CONNECT: {discord.version_info}")
            logger.info(f"CONNECT: Latency: {self.latency * 1000} ms")
            self.connected = True

        await self.sync_commands()
        logger.info("CONNECT: Commands synced")

    async def on_disconnect(self) -> None:
        """Perform tasks when the bot disconnects from Discord."""
        logger.info("DISCONNECT: Bot disconnected")
        self.connected = False

    async def on_ready(self) -> None:
        """Override the on_ready method to initialize essential bot tasks.

        Perform core setup operations when the bot becomes ready. Wait for full
        connection, set the bot's presence, initialize the database, and provision
        connected guilds. Set the start time for uptime calculations and manage
        version tracking in the database. Initiate the web server if enabled in
        the configuration.

        Additional functionality is implemented in the on_ready listener within
        event_listener.py.
        """
        await self.wait_until_ready()
        while not self.connected:
            logger.warning("CONNECT: Waiting for connection...")
            await asyncio.sleep(10)

        # Needed for computing uptime
        self.start_time = datetime.now(UTC)

        if not self.welcomed:
            await self.change_presence(
                activity=discord.Activity(type=discord.ActivityType.watching, name="for /help"),
            )

            await self._provision_guilds()

        self.welcomed = True
        logger.info(f"{self.user} is ready")

    async def get_guild_from_id(self, guild_id: int) -> discord.Guild | None:
        """Get a discord guild object from a guild ID.

        Args:
            guild_id (int): The ID of the guild to get.

        Returns:
            discord.Guild | None: The guild with the given ID, or None if it is not found.
        """
        for guild in self.guilds:
            if guild.id == guild_id:
                return guild

        return None

    # Define a custom application context class
    async def get_application_context(
        self,
        interaction: discord.Interaction,
        cls: type[ValentinaContext] = ValentinaContext,
    ) -> discord.ApplicationContext:
        """Override the get_application_context method to use a custom context.

        Return a ValentinaContext instance instead of the default ApplicationContext.
        This allows for custom functionality and attributes specific to the Valentina
        bot to be available in all command interactions.

        Args:
            interaction (discord.Interaction): The interaction object from Discord.
            cls (Type[ValentinaContext], optional): The context class to use. Defaults to ValentinaContext.

        Returns:
            ValentinaContext: A custom application context for Valentina bot interactions.
        """
        return await super().get_application_context(interaction, cls=cls)

    async def get_autocomplete_context(
        self,
        interaction: discord.Interaction,
        cls: type[ValentinaAutocompleteContext] = ValentinaAutocompleteContext,
    ) -> discord.AutocompleteContext:
        """Override the get_autocomplete_context method to use a custom context."""
        return await super().get_autocomplete_context(interaction, cls=cls)

    @tasks.loop(minutes=30)
    async def sync_user_roles(self) -> None:
        """Sync member discord roles with api and database roles."""
        from vclient import users_service
        from vclient.exceptions import NotFoundError

        from vbot.handlers import database_handler

        logger.debug("SYNC: Running sync_user_roles task")

        for guild in self.guilds:
            for member in [x for x in guild.members if not x.bot]:
                role = "PLAYER"

                db_member, _ = await DBUser.update_or_create(
                    discord_user_id=member.id,
                    defaults={"name": member.display_name, "role": role},
                )

                api_user = None
                if db_member.api_user_id:
                    try:
                        api_user = await users_service().get(user_id=db_member.api_user_id)
                    except NotFoundError:
                        continue

                    if api_user:
                        role = api_user.role
                        await database_handler.update_or_create_user(
                            user=api_user,
                            discord_user=member,
                        )
                    else:
                        db_member.api_user_id = None
                        await db_member.save()

                elif member.guild_permissions.administrator:
                    role = "ADMIN"
                elif any(role.name in ("Storyteller", "@Storyteller") for role in member.roles):
                    role = "STORYTELLER"
                elif any(role.name in ("Player", "@Player") for role in member.roles):
                    role = "PLAYER"

                if db_member.role != role:
                    db_member.role = role
                    await db_member.save()

                await set_user_role(bot=self, guild=guild, member=member, role=role)  # type: ignore[arg-type]
