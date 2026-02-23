"""Tests for campaign cog library functions."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tests.factories import make_campaign, make_campaign_book, make_chapter, make_character

pytestmark = pytest.mark.anyio


class TestBuildCampaignListText:
    """Tests for build_campaign_list_text()."""

    async def test_returns_none_when_no_campaigns(self, mocker):
        """Verify returns None when no campaigns exist."""
        # Given: no campaigns
        mocker.patch(
            "vbot.cogs.campaign.lib.campaign_handler",
            autospec=True,
        ).list_campaigns = AsyncMock(return_value=[])

        # When: building the campaign list text
        from vbot.cogs.campaign.lib import build_campaign_list_text

        result = await build_campaign_list_text(user_api_id="user-001", guild_name="Test Guild")

        # Then: returns None
        assert result is None

    async def test_builds_text_with_campaigns_books_chapters_characters(self, mocker):
        """Verify formatted text includes campaigns, books, chapters, and characters."""
        # Given: one campaign with one book, one chapter, and one character
        campaign = make_campaign(id="c-001", name="Dark Ages")
        book = make_campaign_book(id="b-001", name="Book One", number=1)
        chapter = make_chapter(id="ch-001", name="The Beginning", number=1)
        character = make_character(id="char-001", name="John Doe")

        mock_campaign_handler = mocker.patch(
            "vbot.cogs.campaign.lib.campaign_handler", autospec=True
        )
        mock_campaign_handler.list_campaigns = AsyncMock(return_value=[campaign])

        mock_book_handler = mocker.patch("vbot.cogs.campaign.lib.book_handler", autospec=True)
        mock_book_handler.list_books = AsyncMock(return_value=[book])

        mock_character_handler = mocker.patch(
            "vbot.cogs.campaign.lib.character_handler", autospec=True
        )
        mock_character_handler.list_characters = AsyncMock(return_value=[character])

        mock_chapters = AsyncMock()
        mock_chapters.list_all = AsyncMock(return_value=[chapter])
        mocker.patch(
            "vbot.cogs.campaign.lib.chapters_service",
            autospec=True,
            return_value=mock_chapters,
        )

        # When: building the campaign list text
        from vbot.cogs.campaign.lib import build_campaign_list_text

        result = await build_campaign_list_text(user_api_id="user-001", guild_name="Test Guild")

        # Then: text contains campaign, book, chapter, and character names
        assert result is not None
        assert "Dark Ages" in result
        assert "Book One" in result
        assert "The Beginning" in result
        assert "John Doe" in result
        assert "Test Guild" in result

    async def test_builds_text_with_no_books(self, mocker):
        """Verify formatted text handles campaigns with no books."""
        # Given: a campaign with no books but one character
        campaign = make_campaign(id="c-001", name="Modern Nights")
        character = make_character(id="char-001", name="Jane Smith")

        mock_campaign_handler = mocker.patch(
            "vbot.cogs.campaign.lib.campaign_handler", autospec=True
        )
        mock_campaign_handler.list_campaigns = AsyncMock(return_value=[campaign])

        mocker.patch("vbot.cogs.campaign.lib.book_handler", autospec=True).list_books = AsyncMock(
            return_value=[]
        )

        mocker.patch(
            "vbot.cogs.campaign.lib.character_handler", autospec=True
        ).list_characters = AsyncMock(return_value=[character])

        # When: building the campaign list text
        from vbot.cogs.campaign.lib import build_campaign_list_text

        result = await build_campaign_list_text(user_api_id="user-001", guild_name="Test Guild")

        # Then: text contains campaign and character but no book section
        assert result is not None
        assert "Modern Nights" in result
        assert "Jane Smith" in result
