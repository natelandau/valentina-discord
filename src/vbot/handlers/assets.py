"""Handlers for assets."""

from __future__ import annotations

from typing import TYPE_CHECKING, assert_never

from loguru import logger
from vclient import (
    books_service,
    campaigns_service,
    chapters_service,
    characters_service,
    users_service,
)

from vbot.db.models.campaign import DBCampaignBook, DBCharacter

if TYPE_CHECKING:
    from vclient.models import Asset

__all__ = ["delete_asset_handler"]


async def _delete_character_asset(asset: Asset, *, user_api_id: str) -> None:
    """Delete a character asset."""
    db_character = await DBCharacter.get_or_none(api_id=asset.parent_id)
    if db_character is None:
        logger.warning("Character not found", asset_id=asset.id)
        return
    await db_character.fetch_related("campaign")

    await characters_service(
        user_id=user_api_id, campaign_id=db_character.campaign.api_id
    ).delete_asset(character_id=asset.parent_id, asset_id=asset.id)


async def _delete_campaign_asset(asset: Asset, *, user_api_id: str) -> None:
    """Delete a campaign asset."""
    await campaigns_service(user_id=user_api_id).delete_asset(
        campaign_id=asset.parent_id, asset_id=asset.id
    )


async def _delete_campaignbook_asset(asset: Asset, *, user_api_id: str) -> None:
    """Delete a campaignbook asset."""
    db_book = await DBCampaignBook.get_or_none(api_id=asset.parent_id)
    if db_book is None:
        logger.warning("Book not found", asset_id=asset.id)
        return
    await db_book.fetch_related("campaign")

    await books_service(user_id=user_api_id, campaign_id=db_book.campaign.api_id).delete_asset(
        book_id=asset.parent_id, asset_id=asset.id
    )


async def _delete_campaignchapter_asset(asset: Asset, *, user_api_id: str) -> None:
    """Delete a campaignchapter asset."""
    async for campaign in campaigns_service(user_id=user_api_id).iter_all():
        async for book in books_service(user_id=user_api_id, campaign_id=campaign.id).iter_all():
            async for chapter in chapters_service(
                user_id=user_api_id, campaign_id=campaign.id, book_id=book.id
            ).iter_all():
                if chapter.id == asset.parent_id:
                    await chapters_service(
                        user_id=user_api_id, campaign_id=campaign.id, book_id=book.id
                    ).delete_asset(chapter_id=asset.parent_id, asset_id=asset.id)
                    return


async def _delete_user_asset(asset: Asset) -> None:
    """Delete a user asset."""
    await users_service().delete_asset(user_id=asset.parent_id, asset_id=asset.id)


async def delete_asset_handler(asset: Asset, *, user_api_id: str) -> None:
    """Delete an asset.

    Args:
        asset (Asset): The asset to delete.
        user_api_id (str): The ID of the user deleting the asset.

    Returns:
        None

    Raises:
        AssertionError: If the asset parent type is not supported.
    """
    match asset.parent_type:
        case "character":
            await _delete_character_asset(asset, user_api_id=user_api_id)
        case "campaign":
            await _delete_campaign_asset(asset, user_api_id=user_api_id)
        case "campaignbook":
            await _delete_campaignbook_asset(asset, user_api_id=user_api_id)
        case "campaignchapter":
            await _delete_campaignchapter_asset(asset, user_api_id=user_api_id)
        case "company":
            ...  # TODO: Implement company asset deletion
        case "user":
            await _delete_user_asset(asset)
        case "unknown":
            logger.warning("Unknown asset parent type", asset_id=asset.id)
        case _:
            assert_never(asset.parent_type)
