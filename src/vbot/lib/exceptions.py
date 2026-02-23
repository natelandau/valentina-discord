"""Custom error types for Valentina."""

from discord import DiscordException

from vbot.constants import LogLevel


class ValentinaError(Exception):
    """Base exception for all Valentina errors with categorization metadata.

    Provide metadata for error handling and logging without coupling
    exceptions to specific presentation layers.

    Attributes:
        category: Error category for routing and filtering
        log_level: Severity level for logging
        default_message: Default message when none is provided
    """

    category: str = "unknown"
    log_level: LogLevel = LogLevel.ERROR
    default_message: str = "An error occurred."

    def __init__(
        self,
        msg: str | None = None,
        e: Exception | None = None,
        *args: str | int,
        **kwargs: int | str | bool,
    ) -> None:
        """Initialize the error with optional message and chained exception.

        Args:
            msg: Custom error message. Uses default_message if None
            e: Exception to chain from
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments
        """
        if not msg:
            msg = self.default_message
        if e:
            msg += f"\nRaised from: {e.__class__.__name__}: {e}"

        super().__init__(msg, *args, **kwargs)


class ValidationError(ValentinaError):
    """Raised when a validation error occurs."""

    category = "user_error"
    log_level = LogLevel.WARNING
    default_message = "A validation error occurred."


class VersionNotFoundError(ValentinaError):
    """Raised when we can't find a version in the changelog."""

    category = "system_error"
    log_level = LogLevel.WARNING
    default_message = "Version not found in changelog."


class MissingConfigurationError(ValentinaError):
    """Raised when a configuration variable is missing."""

    category = "system_error"
    log_level = LogLevel.ERROR
    default_message = "A configuration variable is missing."

    def __init__(
        self,
        msg: str | None = None,
        e: Exception | None = None,
        *args: str | int,
        **kwargs: int | str | bool,
    ) -> None:
        """Initialize with optional configuration variable name."""
        if msg:
            msg = f"A configuration variable is missing: {msg}"

        super().__init__(msg, e, *args, **kwargs)


class BotMissingPermissionsError(ValentinaError, DiscordException):
    """Raised when the bot is missing permissions to run a command."""

    category = "permission_error"
    log_level = LogLevel.ERROR

    def __init__(self, permissions: list[str]) -> None:
        missing = [
            f"**{perm.replace('_', ' ').replace('guild', 'server').title()}**"
            for perm in permissions
        ]
        sub = f"{', '.join(missing[:-1])} and {missing[-1]}" if len(missing) > 1 else missing[0]
        super().__init__(f"I require {sub} permissions to run this command.")


class ChannelTypeError(ValentinaError):
    """Raised when a channel is not the correct type."""

    category = "user_error"
    log_level = LogLevel.WARNING
    default_message = "This channel is not the correct type."


class MessageTooLongError(ValentinaError):
    """Raised when a message is too long to send."""

    category = "system_error"
    log_level = LogLevel.ERROR
    default_message = "Apologies. The message was too long to send. This bug has been reported."


class NoCharacterClassError(ValentinaError):
    """Raised when a character's class is not a valid CharClass enum value."""

    category = "system_error"
    log_level = LogLevel.ERROR
    default_message = "The character class is not valid."


class NoExperienceInCampaignError(ValentinaError):
    """Raised when a no experience is found for a campaign."""

    category = "user_error"
    log_level = LogLevel.WARNING
    default_message = "This user has no experience in this campaign."


class NotEnoughFreebiePointsError(ValentinaError):
    """Raised when there are not enough freebie points to upgrade a trait."""

    category = "user_error"
    log_level = LogLevel.WARNING
    default_message = "Not enough freebie points to upgrade trait."


class TraitAtMinValueError(ValentinaError):
    """Raised when a user tries to update a trait can not be lowered below 0."""

    category = "user_error"
    log_level = LogLevel.WARNING
    default_message = "Trait can not be lowered below 0"


class TraitAtMaxValueError(ValentinaError):
    """Raised when a user tries to update a trait already at max value."""

    category = "user_error"
    log_level = LogLevel.WARNING
    default_message = "Trait is already at max value."


class NotEnoughExperienceError(ValentinaError, DiscordException):
    """Raised when a user does not have enough experience to perform an action."""

    category = "user_error"
    log_level = LogLevel.WARNING
    default_message = "Not enough experience to perform this action."


class S3ObjectExistsError(ValentinaError):
    """Raised when an S3 object already exists."""

    category = "user_error"
    log_level = LogLevel.WARNING
    default_message = "A file with that name already exists."


class ServiceDisabledError(ValentinaError, DiscordException):
    """Raised when a service is disabled."""

    category = "user_error"
    log_level = LogLevel.WARNING
    default_message = "The requested service is disabled"

    def __init__(
        self,
        msg: str | None = None,
        e: Exception | None = None,
        *args: str | int,
        **kwargs: int | str | bool,
    ) -> None:
        """Initialize with optional service name."""
        if msg:
            msg = f"The requested service is disabled: {msg}"

        super().__init__(msg, e, *args, **kwargs)


class TraitExistsError(ValentinaError, DiscordException):
    """Raised when adding a trait that already exists on a character."""

    category = "user_error"
    log_level = LogLevel.WARNING
    default_message = "This trait already exists on this character."


class URLNotAvailableError(ValentinaError, DiscordException):
    """Raised when a URL is not available."""

    category = "user_error"
    log_level = LogLevel.WARNING
    default_message = "The requested URL is not available."


class NoCTXError(ValentinaError):
    """Raised when the context was not passed."""

    category = "system_error"
    log_level = LogLevel.ERROR
    default_message = "The context object was not passed."


class UserNotLinkedError(ValentinaError, DiscordException):
    """Raised when a user is not linked to a Valentina user."""

    category = "user_error"
    log_level = LogLevel.WARNING
    default_message = "The user is not linked to a Valentina user."


class CancellationActionError(ValentinaError, DiscordException):
    """Raised when a cancellation action is performed."""

    category = "user_error"
    log_level = LogLevel.INFO
    default_message = "Cancellation successful."
