"""Run the application."""

import asyncio
import sys

import discord
from loguru import logger
from tortoise import Tortoise
from vclient import VClient

from vbot import __version__
from vbot.bot import Valentina
from vbot.config.base import settings
from vbot.config.db import DB_CONFIG
from vbot.lib.logging import instantiate_logger


async def run_bot() -> None:
    """Run the bot."""
    instantiate_logger(settings.log_level)
    logger.info(f"Starting bot version {__version__}")

    await Tortoise.init(config=DB_CONFIG)
    await Tortoise.generate_schemas(safe=True)

    vclient = VClient(
        base_url=settings.api.base_url,
        api_key=settings.api.api_key,
        default_company_id=settings.api.default_company_id,
        auto_idempotency_keys=settings.api.auto_idempotency_keys,
        auto_retry_rate_limit=settings.api.auto_retry_rate_limit,
        max_retries=settings.api.max_retries,
        retry_delay=settings.api.retry_delay,
        timeout=settings.api.timeout,
    )

    bot = Valentina(
        debug_guilds=[int(g) for g in settings.discord.guilds],
        intents=discord.Intents.all(),
        owner_ids=[int(o) for o in settings.discord.owner_ids],
        command_prefix="∑",  # Effectively remove the command prefix by setting it to 'sigma' which no one will ever use
        version=__version__,
    )

    try:
        await bot.start(settings.discord.token)
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error starting bot: {e}")
        await bot.close()
        await vclient.close()
        await Tortoise.close_connections()
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt detected, shutting down...")
        await bot.close()
        await vclient.close()
        await Tortoise.close_connections()
        sys.exit(0)
    finally:
        await bot.close()
        await vclient.close()
        await Tortoise.close_connections()
        sys.exit(0)


def main() -> None:
    """Main function."""
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
