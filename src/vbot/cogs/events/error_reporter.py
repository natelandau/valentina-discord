"""Error reporter for the application."""

import traceback

import discord
from discord.ext import commands
from loguru import logger
from vclient.exceptions import NotFoundError as VClientNotFoundError
from vclient.exceptions import RequestValidationError as VClientRequestValidationError
from vclient.exceptions import ValidationError as VClientValidationError

from vbot.constants import EmbedColor, LogLevel
from vbot.lib import exceptions
from vbot.views import user_error_embed


class ErrorReporter:
    """Error handler reports errors to channels and logs."""

    def __init__(self) -> None:
        """Initialize the error reporter."""
        self.bot: commands.Bot = None
        self.channel: discord.TextChannel = None

    @staticmethod
    def _handle_known_exceptions(
        ctx: discord.ApplicationContext,
        error: Exception,
    ) -> tuple[str | None, str | None, bool]:
        """Handle known exceptions and return user message, log message, and traceback flag.

        Args:
            ctx (discord.ApplicationContext): The context in which the command was called.
            error (Exception): The exception that was raised.

        Returns:
            tuple[str | None, str | None, bool]: The user message, log message, and a boolean to show traceback.
        """
        # Exception configurations: (user_msg, log_msg, show_traceback)
        # Using tuples of exception types as keys for grouping related exceptions
        exception_handlers: dict[
            type[Exception] | tuple[type[Exception], ...],
            tuple[str | None, str | None, bool],
        ] = {
            # Permission errors - logged and reported, no traceback
            (
                commands.errors.MissingAnyRole,
                commands.errors.MissingRole,
                commands.MissingPermissions,
                commands.NotOwner,
            ): (
                "Sorry, you don't have permission to run this command!",
                f"COMMAND: `{ctx.user.display_name}` tried to run `/{ctx.command}` without the correct permissions",
                False,
            ),
            # User-facing validation errors - reported only, no logs/traceback
            (
                exceptions.ChannelTypeError,
                exceptions.NotEnoughExperienceError,
                exceptions.NoExperienceInCampaignError,
                exceptions.URLNotAvailableError,
                exceptions.ServiceDisabledError,
                exceptions.S3ObjectExistsError,
                exceptions.TraitExistsError,
                exceptions.TraitAtMaxValueError,
                exceptions.TraitAtMinValueError,
                exceptions.NotEnoughFreebiePointsError,
                exceptions.UserNotLinkedError,
                exceptions.CancellationActionError,
            ): (
                str(error),
                None,
                False,
            ),
            # Simple command errors
            (commands.BadArgument,): (
                "Invalid argument provided",
                None,
                False,
            ),
            (commands.NoPrivateMessage,): (
                "Sorry, this command can only be run in a server!",
                None,
                False,
            ),
        }

        # Check simple handlers first
        for exception_types, (user_msg, log_msg, show_traceback) in exception_handlers.items():
            if isinstance(error, exception_types):
                return user_msg, log_msg, show_traceback

        # Handle complex cases that need custom context-dependent logic
        return ErrorReporter._handle_complex_exceptions(ctx, error)

    @staticmethod
    def _handle_complex_exceptions(  # noqa: C901, PLR0911
        ctx: discord.ApplicationContext,
        error: Exception,
    ) -> tuple[str | None, str | None, bool]:
        """Handle exceptions that require custom context-dependent logic.

        Args:
            ctx (discord.ApplicationContext): The context in which the command was called.
            error (Exception): The exception that was raised.

        Returns:
            tuple[str | None, str | None, bool]: The user message, log message, and a boolean to show traceback.
        """
        if isinstance(error, VClientNotFoundError):
            return (
                "An API error occurred. This is likely a bug and has been logged.",
                f"API CLIENT ERROR: {error.status_code} {error.title}: {error.detail} for {error.instance} {getattr(error, 'invalid_parameters', '')}",
                False,
            )

        if isinstance(error, VClientValidationError):
            return (
                str(error.detail),
                f"VALIDATION ERROR: {error.detail}",
                False,
            )

        if isinstance(error, VClientRequestValidationError):
            return (
                "Validation error occurred. Please check your input and try again.",
                f"{error.message}",
                False,
            )

        if isinstance(error, FileNotFoundError):
            return (
                "Sorry, I couldn't find that file. This is likely a bug and has been reported.",
                f"ERROR: `{ctx.user.display_name}` tried to run `/{ctx.command}` and a file was not found",
                True,
            )

        if isinstance(error, exceptions.MissingConfigurationError):
            return (
                "Sorry, something went wrong. This has been reported.",
                f"ERROR: `{ctx.user.display_name}` tried to run `/{ctx.command}` and a configuration variable was not found",
                True,
            )

        if isinstance(error, exceptions.NoCharacterClassError):
            return (
                "Sorry, something went wrong. This has been reported",
                f"ERROR: `{ctx.user.display_name}` tried to run `/{ctx.command}` and a character class was not found",
                True,
            )

        if isinstance(error, exceptions.MessageTooLongError):
            return (
                "Message too long to send. This is a bug has been reported.",
                "ERROR: Message too long to send. Check the logs for the message.",
                True,
            )

        if isinstance(error, exceptions.BotMissingPermissionsError):
            return (
                "Sorry, I don't have permission to run this command!",
                f"ERROR: Bot tried to run `/{ctx.command}` without the correct permissions",
                True,
            )

        if isinstance(error, exceptions.NoCTXError):
            return (
                "Sorry, something went wrong. This has been reported.",
                "ERROR: No context provided",
                True,
            )

        if isinstance(error, discord.errors.DiscordServerError):
            return (
                "Discord server error detected",
                "SERVER: Discord server error detected",
                True,
            )

        if isinstance(error, exceptions.ValidationError):
            return (
                "The data provided is invalid. Please check your input and try again.",
                None,
                False,
            )

        return None, None, False

    async def report_error(self, ctx: discord.ApplicationContext, error: Exception) -> None:
        """Report an error to the error log channel and application log.

        Args:
            ctx (Union[discord.ApplicationContext, discord.Interaction]): The context of the command.
            error (Exception): The exception to be reported.

        Returns:
            None
        """
        user_msg = None
        log_msg = None
        show_traceback = False

        error = getattr(error, "original", error)
        respond = (
            ctx.respond
            if isinstance(ctx, discord.ApplicationContext)
            else (ctx.followup.send if ctx.response.is_done() else ctx.response.send_message)
        )

        user_msg, log_msg, show_traceback = self._handle_known_exceptions(ctx, error)

        # Handle unknown exceptions
        if not user_msg and not log_msg and not show_traceback:
            user_msg = "An error has occurred. This is a bug and has been reported."
            log_msg = f"A `{error.__class__.__name__}` error has occurred. Check the logs for more information."
            show_traceback = True

        # Send the messages
        if user_msg:
            embed_message = user_error_embed(ctx, user_msg, str(error))  # type: ignore [arg-type]
            try:
                await respond(embed=embed_message, ephemeral=True, delete_after=15)
            except discord.HTTPException:
                await respond(
                    embed=user_error_embed(
                        ctx,  # type: ignore [arg-type]
                        "Message too long to send",
                        "This is a bug has been reported",
                    ),
                    ephemeral=True,
                    delete_after=15,
                )
                log_msg = f"NEW ERROR: Message too long to send. Check the logs for the message.\n\nOriginal error: {error.__class__.__name__}"
                show_traceback = True

        if log_msg:
            # Determine log level from exception if it's a ValentinaError
            if isinstance(error, exceptions.ValentinaError):
                log_level = error.log_level
            else:
                log_level = LogLevel.ERROR

            # Log the message with appropriate level and traceback

            log_context = (
                logger.opt(exception=error) if show_traceback else logger.opt(exception=None)
            )
            log_context.log(log_level.value, log_msg)

            # embed = await self._error_log_embed(ctx, log_msg, error)  # noqa: ERA001
            # await ctx.post_to_error_log(embed, error)  # type: ignore [attr-defined]  # noqa: ERA001

        if show_traceback:
            logger.opt(exception=error).error(f"ERROR: {error}")

    @staticmethod
    async def _error_log_embed(
        ctx: discord.ApplicationContext | discord.Interaction,
        msg: str,
        error: Exception,
    ) -> discord.Embed:
        """Create an embed for errors."""
        description = f"{msg}\n"
        description += "```"
        description += "\n".join(traceback.format_exception(error))
        description += "```"

        # If we can, we use the command name to try to pinpoint where the error
        # took place. The stack trace usually makes this clear, but not always!
        if isinstance(ctx, discord.ApplicationContext):
            command_name = ctx.command.qualified_name.upper()
        else:
            command_name = "INTERACTION"

        error_name = type(error).__name__

        embed = discord.Embed(
            title=f"{command_name}: {error_name}",
            description=description,
            color=EmbedColor.INFO.value,
            timestamp=discord.utils.utcnow(),
        )

        if ctx.guild is not None:
            guild_name = ctx.guild.name
            guild_icon = ctx.guild.icon or ""
        else:
            guild_name = "DM"
            guild_icon = ""

        embed.set_author(name=f"{ctx.user.name} on {guild_name}", icon_url=guild_icon)

        return embed


reporter = ErrorReporter()
