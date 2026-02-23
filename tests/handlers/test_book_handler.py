"""Tests for the book API handler."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tests.factories import make_campaign_book
from vbot.db.models import DBCampaign, DBCampaignBook
from vbot.handlers.book import book_handler

pytestmark = pytest.mark.anyio


class TestListBooks:
    """Tests for BookAPIHandler.list_books()."""

    async def test_returns_books(self, db, mock_books_service):
        """Verify delegates to API with correct args and syncs to DB."""
        # Given: a campaign exists in the DB
        await DBCampaign.create(api_id="camp-001", name="Test Campaign")

        # Given: the API returns books
        books = [
            make_campaign_book(id="b-001", name="Book One", number=1, campaign_id="camp-001"),
            make_campaign_book(id="b-002", name="Book Two", number=2, campaign_id="camp-001"),
        ]
        mock_books_service._service.list_all.return_value = books

        # When: listing books
        result = await book_handler.list_books(user_api_id="user-001", campaign_api_id="camp-001")

        # Then: API was called with correct params
        mock_books_service.assert_called_once_with(user_id="user-001", campaign_id="camp-001")
        assert len(result) == 2

        # Then: books are synced to DB
        assert await DBCampaignBook.filter(api_id="b-001").count() == 1
        assert await DBCampaignBook.filter(api_id="b-002").count() == 1


class TestGetBook:
    """Tests for BookAPIHandler.get_book()."""

    async def test_returns_book(self, db, mock_books_service):
        """Verify delegates to API and syncs to DB."""
        # Given: a campaign exists in the DB
        await DBCampaign.create(api_id="camp-001", name="Test Campaign")

        # Given: the API returns a book
        book = make_campaign_book(id="b-001", name="The Book", campaign_id="camp-001")
        mock_books_service._service.get.return_value = book

        # When: getting a book
        result = await book_handler.get_book(
            user_api_id="user-001", campaign_api_id="camp-001", book_api_id="b-001"
        )

        # Then: API was called correctly
        mock_books_service._service.get.assert_awaited_once_with("b-001")
        assert result.name == "The Book"

        # Then: book is synced to DB
        assert await DBCampaignBook.filter(api_id="b-001").count() == 1


class TestCreateBook:
    """Tests for BookAPIHandler.create_book()."""

    async def test_creates_book(self, db, mock_books_service, mock_valentina_context):
        """Verify API called, DB synced, and channel manager invoked."""
        # Given: a campaign exists in the DB
        await DBCampaign.create(api_id="camp-001", name="Test Campaign")

        # Given: the API returns a created book
        book = make_campaign_book(id="b-001", name="New Book", campaign_id="camp-001")
        mock_books_service._service.create.return_value = book

        # Given: channel manager is mocked
        mock_cm = AsyncMock()

        # When: creating a book
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "vbot.handlers.book.ChannelManager",
                lambda guild: mock_cm,
            )
            result = await book_handler.create_book(
                mock_valentina_context, "camp-001", "New Book", "A new book"
            )

        # Then: API was called with correct args
        mock_books_service._service.create.assert_awaited_once_with(
            name="New Book", description="A new book"
        )

        # Then: book is synced to DB
        assert await DBCampaignBook.filter(api_id="b-001").count() == 1

        # Then: channel manager was invoked
        mock_cm.confirm_campaign_channels.assert_awaited_once()
        assert result.name == "New Book"


class TestUpdateBook:
    """Tests for BookAPIHandler.update_book()."""

    async def test_updates_book_with_rename(self, db, mock_books_service, mock_valentina_context):
        """Verify channel manager called on rename."""
        # Given: a campaign and book exist in the DB
        db_campaign = await DBCampaign.create(api_id="camp-001", name="Test Campaign")
        await DBCampaignBook.create(api_id="b-001", name="Old Name", number=1, campaign=db_campaign)

        # Given: the API returns an updated book
        book = make_campaign_book(id="b-001", name="New Name", campaign_id="camp-001")
        mock_books_service._service.update.return_value = book

        # Given: channel manager is mocked
        mock_cm = AsyncMock()

        # When: updating with a new name
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "vbot.handlers.book.ChannelManager",
                lambda guild: mock_cm,
            )
            result = await book_handler.update_book(
                mock_valentina_context, "camp-001", "b-001", book_name="New Name"
            )

        # Then: channel manager was invoked for rename
        mock_cm.confirm_book_channel.assert_awaited_once()
        mock_cm.sort_campaign_channels.assert_awaited_once()
        assert result.name == "New Name"

    async def test_updates_book_no_rename(self, db, mock_books_service, mock_valentina_context):
        """Verify channel manager NOT called when book_name is None."""
        # Given: a campaign and book exist in the DB
        db_campaign = await DBCampaign.create(api_id="camp-001", name="Test Campaign")
        await DBCampaignBook.create(
            api_id="b-001", name="Same Name", number=1, campaign=db_campaign
        )

        # Given: the API returns the book
        book = make_campaign_book(id="b-001", name="Same Name", campaign_id="camp-001")
        mock_books_service._service.update.return_value = book

        # Given: channel manager is mocked
        mock_cm = AsyncMock()

        # When: updating without a name change
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "vbot.handlers.book.ChannelManager",
                lambda guild: mock_cm,
            )
            await book_handler.update_book(
                mock_valentina_context,
                "camp-001",
                "b-001",
                book_description="Updated desc",
            )

        # Then: channel manager was NOT invoked
        mock_cm.confirm_book_channel.assert_not_awaited()
        mock_cm.sort_campaign_channels.assert_not_awaited()


class TestDeleteBook:
    """Tests for BookAPIHandler.delete_book()."""

    async def test_deletes_book(self, db, mock_books_service, mock_valentina_context):
        """Verify API called, DB record deleted, and channels refreshed."""
        # Given: a campaign and book exist in the DB
        db_campaign = await DBCampaign.create(api_id="camp-001", name="Test Campaign")
        await DBCampaignBook.create(
            api_id="b-001", name="Doomed Book", number=1, campaign=db_campaign
        )

        # Given: channel manager is mocked
        mock_cm = AsyncMock()

        # When: deleting the book
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "vbot.handlers.book.ChannelManager",
                lambda guild: mock_cm,
            )
            await book_handler.delete_book(mock_valentina_context, "camp-001", "b-001")

        # Then: API delete was called
        mock_books_service._service.delete.assert_awaited_once_with("b-001")

        # Then: DB record is removed
        assert await DBCampaignBook.filter(api_id="b-001").count() == 0

        # Then: channel manager refreshed campaign channels
        mock_cm.confirm_campaign_channels.assert_awaited_once()


class TestRenumberBook:
    """Tests for BookAPIHandler.renumber_book()."""

    async def test_renumbers_book(self, db, mock_books_service, mock_valentina_context):
        """Verify API renumber called, list refreshed, and channels updated."""
        # Given: a campaign exists in the DB
        db_campaign = await DBCampaign.create(api_id="camp-001", name="Test Campaign")
        await DBCampaignBook.create(api_id="b-001", name="Book One", number=1, campaign=db_campaign)

        # Given: the API returns the renumbered book
        book = make_campaign_book(id="b-001", name="Book One", number=3, campaign_id="camp-001")
        mock_books_service._service.renumber.return_value = book

        # Given: list_all returns updated books (called by list_books internally)
        mock_books_service._service.list_all.return_value = [book]

        # Given: channel manager is mocked
        mock_cm = AsyncMock()

        # When: renumbering the book
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "vbot.handlers.book.ChannelManager",
                lambda guild: mock_cm,
            )
            result = await book_handler.renumber_book(
                mock_valentina_context, "camp-001", "b-001", 3
            )

        # Then: API renumber was called
        mock_books_service._service.renumber.assert_awaited_once_with("b-001", 3)

        # Then: list_books was called to refresh all books
        mock_books_service._service.list_all.assert_awaited_once()

        # Then: channel manager updated channels
        mock_cm.confirm_campaign_channels.assert_awaited_once()
        assert result.number == 3
