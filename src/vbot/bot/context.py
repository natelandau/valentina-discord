"""Subclass discord.ApplicationContext to create custom application context."""

from __future__ import annotations

import inspect
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import discord
from loguru import logger

from vbot.constants import EmbedColor, LogLevel
from vbot.db.models import DBUser
from vbot.lib import exceptions

if TYPE_CHECKING:
    from vbot.bot import Valentina


class ValentinaAutocompleteContext(discord.AutocompleteContext):
    """Extend discord.AutocompleteContext with Valentina-specific functionality.

    Provide custom methods and properties for handling Valentina's autocomplete context.
    Implement logging capabilities and embed creation for consistent message formatting.
    """

    if TYPE_CHECKING:
        bot: Valentina

    async def get_api_user(self) -> DBUser | None:
        """Get the API user from the context."""
        if not self.interaction.user.id:
            msg = "You are not linked to a Valentina user. Talk to your server administrator to link your account."
            raise exceptions.UserNotLinkedError(msg)

        api_user = await DBUser.get_or_none(discord_user_id=self.interaction.user.id)

        if not api_user:
            msg = "You are not linked to a Valentina user. Talk to your server administrator to link your account."
            raise exceptions.UserNotLinkedError(msg)

        return api_user

    async def get_api_user_id(self) -> str:
        """Get the API user ID from the context."""
        api_user = await self.get_api_user()
        return api_user.api_user_id


class ValentinaContext(discord.ApplicationContext):
    """Extend discord.ApplicationContext with Valentina-specific functionality.

    Provide custom methods and properties for handling Valentina's command context.
    Implement logging capabilities and embed creation for consistent message formatting.
    """

    if TYPE_CHECKING:
        bot: Valentina

    async def get_api_user(self) -> DBUser | None:
        """Get the API user from the context."""
        api_user = await DBUser.get_or_none(discord_user_id=self.author.id)

        if not api_user:
            msg = "You are not linked to a Valentina user. Talk to your server administrator to link your account."
            raise exceptions.UserNotLinkedError(msg)

        return api_user

    async def get_api_user_id(self) -> str:
        """Get the API user ID from the context."""
        api_user = await self.get_api_user()
        return api_user.api_user_id

    def log_command(self, msg: str, level: LogLevel = LogLevel.INFO) -> None:  # pragma: no cover
        """Log the executed command with contextual information.

        Log the command details to both console and log file, including the author,
        command name, and channel where it was executed. Determine the appropriate
        log level and construct a detailed log message with the command's context.
        Use introspection to identify the calling function and create a hierarchical
        logger name for better traceability.
        """
        author = f"@{self.author.display_name}" if hasattr(self, "author") else None
        command = f"'/{self.command.qualified_name}'" if hasattr(self, "command") else None
        channel = f"#{self.channel.name}" if hasattr(self, "channel") else None  # type: ignore [union-attr]

        extras = {"author": author, "command": command, "channel": channel}

        if (
            inspect.stack()[1].function == "post_to_audit_log"
            and inspect.stack()[2].function == "confirm_action"
        ):
            name1 = inspect.stack()[3].filename.split("/")[-3].split(".")[0]
            name2 = inspect.stack()[3].filename.split("/")[-2].split(".")[0]
            name3 = inspect.stack()[3].filename.split("/")[-1].split(".")[0]
            new_name = f"{name1}.{name2}.{name3}"
        elif inspect.stack()[1].function == "post_to_audit_log":
            name1 = inspect.stack()[2].filename.split("/")[-3].split(".")[0]
            name2 = inspect.stack()[2].filename.split("/")[-2].split(".")[0]
            name3 = inspect.stack()[2].filename.split("/")[-1].split(".")[0]
            new_name = f"{name1}.{name2}.{name3}"
        else:
            name1 = inspect.stack()[1].filename.split("/")[-3].split(".")[0]
            name2 = inspect.stack()[1].filename.split("/")[-2].split(".")[0]
            name3 = inspect.stack()[1].filename.split("/")[-1].split(".")[0]
            new_name = f"{name1}.{name2}.{name3}"

        logger.patch(lambda r: r.update(name=new_name)).log(  # type: ignore [call-arg]
            level.value, msg, **extras
        )

    def _message_to_embed(self, message: str) -> discord.Embed:  # pragma: no cover
        """Convert a string message to a Discord embed.

        Create a Discord embed object from the given message string. Set the embed's
        color based on the command category, add a timestamp, and include footer
        information about the command, user, and channel. The embed's title is set
        to the input message.

        Args:
            message (str): The message to be used as the embed's title.

        Returns:
            discord.Embed: A fully formatted Discord embed object.
        """
        # Set color based on command
        if hasattr(self, "command") and (
            self.command.qualified_name.startswith("admin")
            or self.command.qualified_name.startswith("owner")
            or self.command.qualified_name.startswith("developer")
        ):
            color = EmbedColor.WARNING.value
        elif hasattr(self, "command") and self.command.qualified_name.startswith("storyteller"):
            color = EmbedColor.SUCCESS.value
        elif hasattr(self, "command") and self.command.qualified_name.startswith("gameplay"):
            color = EmbedColor.GRAY.value
        elif hasattr(self, "command") and self.command.qualified_name.startswith("campaign"):
            color = EmbedColor.DEFAULT.value
        else:
            color = EmbedColor.INFO.value

        embed = discord.Embed(title=message, color=color)
        embed.timestamp = datetime.now(UTC)

        footer = ""
        if hasattr(self, "command"):
            footer += f"Command: /{self.command.qualified_name}"
        else:
            footer += "Command: Unknown"

        if hasattr(self, "author"):
            footer += f" | User: @{self.author.display_name}"
        if hasattr(self, "channel"):
            footer += f" | Channel: #{self.channel.name}"  # type: ignore [union-attr]

        embed.set_footer(text=footer)

        return embed

    # async def post_to_error_log(
    #     self,
    #     message: str | discord.Embed,
    #     error: Exception,
    # ) -> None:  # pragma: no cover
    #     """Post an error message or embed to the guild's error log channel.

    #     Convert the input message to an embed if it's a string. Attempt to send the
    #     error information to the guild's designated error log channel. If the message
    #     is too long, send a truncated version with basic error details.

    #     Args:
    #         message (str | discord.Embed): The error message or embed to send.
    #         error (Exception): The exception that triggered the error log.

    #     Raises:
    #         discord.DiscordException: If the error message cannot be sent to the channel.
    #     """
    #     # Get the database guild object and error log channel
    #     db_guild = await DBGuild.get(self.guild.id)  # noqa: ERA001
    #     error_log_channel = db_guild.fetch_error_log_channel(self.guild)  # noqa: ERA001

    #     # Log to the error log channel if it exists and is enabled
    #     if error_log_channel:
    #         embed = self._message_to_embed(message) if isinstance(message, str) else message  # noqa: ERA001
    #         try: # noqa: ERA001
    #             await error_log_channel.send(embed=embed) # noqa: ERA001
    #         except discord.HTTPException: # noqa: ERA001
    #             embed = discord.Embed(title=f"A {error.__class__.__name__} exception was raised",
    #                 description="The error was too long to fit! Check the logs for full traceback",  # noqa: ERA001
    #                 color=EmbedColor.ERROR.value,  # noqa: ERA001
    #                 timestamp=discord.utils.utcnow(),)
    #             await error_log_channel.send(embed=embed)  # noqa: ERA001

    # async def post_to_audit_log(self, message: str | discord.Embed) -> None:  # pragma: no cover
    #     """Send a message to the guild's audit log channel.

    #     Convert the input message to an embed if it's a string, otherwise send the provided embed. Log the message content to the command log. Attempt to send the message to the guild's designated audit log channel.

    #     Args:
    #         message (str | discord.Embed): The message or embed to send to the audit log.

    #     Raises:
    #         errors.MessageTooLongError: If the message exceeds Discord's character limit.
    #     """
    #     # Get the database guild object and error log channel
    #     db_guild = await DBGuild.get(self.guild.id) # noqa: ERA001
    #     audit_log_channel = db_guild.fetch_audit_log_channel(self.guild) # noqa: ERA001

    #     if isinstance(message, str):
    #         self.log_command(message, LogLevel.INFO) # noqa: ERA001

    #     if isinstance(message, discord.Embed):
    #         self.log_command(f"{message.title} {message.description}", LogLevel.INFO) # noqa: ERA001

    #     if audit_log_channel:
    #         embed = self._message_to_embed(message) if isinstance(message, str) else message # noqa: ERA001

    #         try: # noqa: ERA001
    #             await audit_log_channel.send(embed=embed) # noqa: ERA001
    #         except discord.HTTPException as e: # noqa: ERA001
    #             raise errors.MessageTooLongError from e
