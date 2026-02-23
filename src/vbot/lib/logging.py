"""Logging utilities for Valentina."""

import logging
import sys

from loguru import logger

from vbot.config.base import settings
from vbot.constants import LogLevel

__all__ = ("instantiate_logger",)


def instantiate_logger(log_level: LogLevel | None = None) -> None:  # pragma: no cover
    """Instantiate the Loguru logger for Valentina.

    Configure the logger with the specified verbosity level, log file path,
    and whether to log to a file.

    Args:
        log_level (LogLevel): The verbosity level for the logger.

    Returns:
        None
    """
    log_level_name = log_level.value if log_level else settings.log_level.value

    # Configure Loguru
    logger.remove()
    logger.add(
        sys.stderr,
        level=log_level_name,
        colorize=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>: <level>{message}</level> | <level>{extra}</level>",
        enqueue=True,
    )
    if settings.log_file_path:
        logger.add(
            settings.log_file_path,
            level=log_level_name,
            rotation="10 MB",
            retention=3,
            compression="zip",
            enqueue=True,
        )

    if settings.api.enable_logs:
        logger.enable("vclient")

    # Intercept standard discord.py logs and redirect to Loguru
    logging.getLogger("asyncio").setLevel(level="ERROR")
    for service in [
        "discord.http",
        "discord.gateway",
        "discord.webhook",
        "discord.client",
        "httpcore",
        "httpx",
        "aiosqlite",
        "tortoise",
    ]:
        logging.getLogger(service).setLevel(level="WARNING")

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)


class InterceptHandler(logging.Handler):
    """Intercepts standard logging and redirects to Loguru.

    This class is a logging handler that intercepts standard logging messages and redirects them to Loguru, a third-party logging library. When a logging message is emitted, this handler determines the corresponding Loguru level for the message and logs it using the Loguru logger.

    Methods:
        emit: Intercepts standard logging and redirects to Loguru.

    Examples:
    To use the InterceptHandler with the Python logging module:
    ```
    import logging
    from logging import StreamHandler

    from loguru import logger

    # Create a new InterceptHandler and add it to the Python logging module.
    intercept_handler = InterceptHandler()
    logging.basicConfig(handlers=[StreamHandler(), intercept_handler], level=logging.INFO)

    # Log a message using the Python logging module.
    logging.info("This message will be intercepted by the InterceptHandler and logged using Loguru.")
    ```
    """

    @staticmethod
    def emit(record: logging.LogRecord) -> None:
        """Intercepts standard logging and redirects to Loguru.

        This method is called by the Python logging module when a logging message is emitted. It intercepts the message and redirects it to Loguru, a third-party logging library. The method determines the corresponding Loguru level for the message and logs it using the Loguru logger.

        Args:
            record: A logging.LogRecord object representing the logging message.
        """
        # Get corresponding Loguru level if it exists.
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno  # type: ignore [assignment]

        # Find caller from where originated the logged message.
        frame, depth = sys._getframe(6), 6  # noqa: SLF001
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())
