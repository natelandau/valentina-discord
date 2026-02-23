"""Library functions for the admin cog."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from vbot.db.models import DBCampaign, DBCampaignBook, DBCharacter
from vbot.handlers import book_handler, campaign_handler, character_handler, database_handler
from vbot.lib.channel_mngr import ChannelManager

if TYPE_CHECKING:
    import discord
    from vclient.models import Campaign


async def _sync_campaign_entities(
    campaign: Campaign,
    user_api_id: str,
    book_api_ids: list[str],
    character_api_ids: list[str],
) -> None:
    """Sync books and characters for a single campaign from the API to local DB.

    Args:
        campaign: The API campaign to sync entities for.
        user_api_id: The API user ID for authentication.
        book_api_ids: Accumulator for synced book IDs (mutated in place).
        character_api_ids: Accumulator for synced character IDs (mutated in place).
    """
    await database_handler.update_or_create_campaign(campaign)

    all_api_books = await book_handler.list_books(
        user_api_id=user_api_id, campaign_api_id=campaign.id
    )
    for book in all_api_books:
        await database_handler.update_or_create_book(book)
    book_api_ids.extend([book.id for book in all_api_books])

    for character_type in ("PLAYER", "STORYTELLER"):
        characters = await character_handler.list_characters(
            campaign_api_id=campaign.id, user_api_id=user_api_id, character_type=character_type
        )
        for character in characters:
            await database_handler.update_or_create_character(character)
        character_api_ids.extend([c.id for c in characters])


async def _prune_stale_records(
    api_campaign_ids: list[str],
    book_api_ids: list[str],
    character_api_ids: list[str],
) -> None:
    """Delete DB records that no longer exist in the API.

    Args:
        api_campaign_ids: IDs of campaigns that exist in the API.
        book_api_ids: IDs of books that exist in the API.
        character_api_ids: IDs of characters that exist in the API.
    """
    for db_campaign in await DBCampaign.all():
        if db_campaign.api_id not in api_campaign_ids:
            logger.info(f"Delete campaign {db_campaign.name} ({db_campaign.api_id}) from database.")
            await db_campaign.delete()

    for db_book in await DBCampaignBook.all():
        if db_book.api_id not in book_api_ids:
            logger.info(f"Delete book {db_book.name} ({db_book.api_id}) from database.")
            await db_book.delete()

    for db_character in await DBCharacter.all():
        if db_character.api_id not in character_api_ids:
            logger.info(
                f"Delete character {db_character.name} ({db_character.api_id}) from database."
            )
            await db_character.delete()


async def resync_all_data(
    user_api_id: str,
    guild: discord.Guild,
) -> list[str]:
    """Sync all API data to local DB, prune stale records, and rebuild campaign channels.

    Fetches all campaigns, books, and characters from the API, syncs them to the
    local SQLite cache, removes any stale DB records that no longer exist in the API,
    and rebuilds Discord campaign channels.

    Args:
        user_api_id: The API user ID for authentication.
        guild: The Discord guild for channel management.

    Returns:
        Channel manager messages describing what was rebuilt.
    """
    all_api_campaigns = await campaign_handler.list_campaigns(user_api_id=user_api_id)
    book_api_ids: list[str] = []
    character_api_ids: list[str] = []

    for campaign in all_api_campaigns:
        await _sync_campaign_entities(campaign, user_api_id, book_api_ids, character_api_ids)

    await _prune_stale_records(
        api_campaign_ids=[c.id for c in all_api_campaigns],
        book_api_ids=book_api_ids,
        character_api_ids=character_api_ids,
    )

    channel_manager = ChannelManager(guild=guild)
    for db_campaign in await DBCampaign.all():
        await channel_manager.confirm_campaign_channels(db_campaign)

    return channel_manager.messages
