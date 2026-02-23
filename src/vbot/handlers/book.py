"""Handler for book API events."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger
from vclient import books_service

from vbot.db.models import DBCampaign, DBCampaignBook
from vbot.lib.channel_mngr import ChannelManager

if TYPE_CHECKING:
    from vclient.models import CampaignBook

    from vbot.bot import ValentinaContext

__all__ = ("book_handler",)


class BookAPIHandler:
    """Handler for book API events."""

    async def _update_or_create_book(self, book: CampaignBook) -> DBCampaignBook:
        """Update or create a book in the database."""
        db_campaign = await DBCampaign.get_or_none(api_id=book.campaign_id)
        db_book, created = await DBCampaignBook.update_or_create(
            api_id=book.id,
            defaults={"name": book.name, "number": book.number, "campaign": db_campaign},
        )
        if created:
            logger.debug(
                "Update or create book in database.",
                book_id=book.id,
                book_name=book.name,
            )
        return db_book

    async def list_books(self, user_api_id: str, campaign_api_id: str) -> list[CampaignBook]:
        """List all books for a campaign.

        Args:
            user_api_id (str): The API ID of the user.
            campaign_api_id (str): The API ID of the campaign.

        Returns:
            list[CampaignBook]: The list of books.
        """
        books = await books_service(user_id=user_api_id, campaign_id=campaign_api_id).list_all()
        for book in books:
            await self._update_or_create_book(book)
        return books

    async def get_book(
        self, user_api_id: str, campaign_api_id: str, book_api_id: str
    ) -> CampaignBook:
        """Get a book by its API ID.

        Args:
            user_api_id (str): The API ID of the user.
            campaign_api_id (str): The API ID of the campaign.
            book_api_id (str): The API ID of the book.

        Returns:
            CampaignBook: The book.
        """
        book = await books_service(user_id=user_api_id, campaign_id=campaign_api_id).get(
            book_api_id
        )
        await self._update_or_create_book(book)
        return book

    async def create_book(
        self, ctx: ValentinaContext, campaign_api_id: str, book_name: str, book_description: str
    ) -> CampaignBook:
        """Create a book."""
        user_api_id = await ctx.get_api_user_id()
        book = await books_service(user_id=user_api_id, campaign_id=campaign_api_id).create(
            name=book_name, description=book_description
        )
        await self._update_or_create_book(book)

        db_campaign = await DBCampaign.get_or_none(api_id=campaign_api_id)
        channel_manager = ChannelManager(guild=ctx.guild)
        await channel_manager.confirm_campaign_channels(db_campaign)

        return book

    async def update_book(
        self,
        ctx: ValentinaContext,
        campaign_api_id: str,
        book_api_id: str,
        book_name: str | None = None,
        book_description: str | None = None,
    ) -> CampaignBook:
        """Update a book."""
        user_api_id = await ctx.get_api_user_id()
        book = await books_service(user_id=user_api_id, campaign_id=campaign_api_id).update(
            book_api_id, name=book_name, description=book_description
        )

        db_book = await self._update_or_create_book(book)

        if book_name:
            db_campaign = await DBCampaign.get_or_none(api_id=campaign_api_id)
            channel_manager = ChannelManager(guild=ctx.guild)
            await channel_manager.confirm_book_channel(book=db_book, campaign=db_campaign)
            await channel_manager.sort_campaign_channels(db_campaign)

        return book

    async def delete_book(
        self, ctx: ValentinaContext, campaign_api_id: str, book_api_id: str
    ) -> None:
        """Delete a book."""
        user_api_id = await ctx.get_api_user_id()
        await books_service(user_id=user_api_id, campaign_id=campaign_api_id).delete(book_api_id)
        await DBCampaignBook.filter(api_id=book_api_id).delete()

        db_campaign = await DBCampaign.get_or_none(api_id=campaign_api_id)
        if db_campaign:
            channel_manager = ChannelManager(guild=ctx.guild)
            await channel_manager.confirm_campaign_channels(db_campaign)

    async def renumber_book(
        self, ctx: ValentinaContext, campaign_api_id: str, book_api_id: str, number: int
    ) -> CampaignBook:
        """Renumber a book."""
        user_api_id = await ctx.get_api_user_id()
        book = await books_service(user_id=user_api_id, campaign_id=campaign_api_id).renumber(
            book_api_id, number
        )

        # Refresh all books in the campaign to update the book numbers
        await self.list_books(user_api_id=user_api_id, campaign_api_id=campaign_api_id)

        db_campaign = await DBCampaign.get_or_none(api_id=campaign_api_id)
        if db_campaign:
            channel_manager = ChannelManager(guild=ctx.guild)
            await channel_manager.confirm_campaign_channels(db_campaign)

        return book


book_handler = BookAPIHandler()
