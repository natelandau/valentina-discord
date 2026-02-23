"""Tests for admin cog library functions."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.factories import make_campaign, make_campaign_book, make_character
from vbot.db.models import DBCampaign, DBCampaignBook, DBCharacter

pytestmark = pytest.mark.anyio


class TestResyncAllData:
    """Tests for resync_all_data()."""

    async def test_syncs_campaigns_books_characters(self, db, mocker):
        """Verify all entity types are fetched from API and synced to DB."""
        # Given: API returns one campaign with one book and one character
        campaign = make_campaign(id="c-001", name="Test Campaign")
        book = make_campaign_book(id="b-001", name="Book One", campaign_id="c-001")
        character = make_character(
            id="char-001", name="John Doe", campaign_id="c-001", type="PLAYER"
        )

        mock_campaign_handler = mocker.patch("vbot.cogs.admin.lib.campaign_handler", autospec=True)
        mock_campaign_handler.list_campaigns = AsyncMock(return_value=[campaign])

        mock_book_handler = mocker.patch("vbot.cogs.admin.lib.book_handler", autospec=True)
        mock_book_handler.list_books = AsyncMock(return_value=[book])

        mock_character_handler = mocker.patch(
            "vbot.cogs.admin.lib.character_handler", autospec=True
        )
        mock_character_handler.list_characters = AsyncMock(return_value=[character])

        mock_db_handler = mocker.patch("vbot.cogs.admin.lib.database_handler", autospec=True)
        mock_db_handler.update_or_create_campaign = AsyncMock()
        mock_db_handler.update_or_create_book = AsyncMock()
        mock_db_handler.update_or_create_character = AsyncMock()

        mock_channel_mgr_instance = AsyncMock()
        mock_channel_mgr_instance.messages = ["Rebuilt channels"]
        mocker.patch(
            "vbot.cogs.admin.lib.ChannelManager",
            return_value=mock_channel_mgr_instance,
        )

        mock_guild = MagicMock()

        # When: running resync
        from vbot.cogs.admin.lib import resync_all_data

        messages = await resync_all_data(user_api_id="user-001", guild=mock_guild)

        # Then: all entity types were synced
        mock_db_handler.update_or_create_campaign.assert_awaited_once_with(campaign)
        mock_db_handler.update_or_create_book.assert_awaited_once_with(book)
        mock_db_handler.update_or_create_character.assert_awaited()

        # Then: character_handler was used (not characters_service directly)
        mock_character_handler.list_characters.assert_awaited()

        # Then: channel manager messages returned
        assert messages == ["Rebuilt channels"]

    async def test_prunes_stale_db_records(self, db, mocker):
        """Verify DB records not in API response are deleted."""
        # Given: API returns one campaign, but DB has two
        campaign = make_campaign(id="c-001", name="Active Campaign")

        await DBCampaign.create(api_id="c-001", name="Active Campaign")
        stale_campaign = await DBCampaign.create(api_id="c-stale", name="Stale Campaign")
        await DBCampaignBook.create(
            api_id="b-stale",
            name="Stale Book",
            number=1,
            campaign=stale_campaign,
        )
        await DBCharacter.create(
            api_id="char-stale",
            name="Stale Char",
            campaign=stale_campaign,
            type="PLAYER",
            status="ALIVE",
        )

        mock_campaign_handler = mocker.patch("vbot.cogs.admin.lib.campaign_handler", autospec=True)
        mock_campaign_handler.list_campaigns = AsyncMock(return_value=[campaign])

        mocker.patch("vbot.cogs.admin.lib.book_handler", autospec=True).list_books = AsyncMock(
            return_value=[]
        )

        mocker.patch(
            "vbot.cogs.admin.lib.character_handler", autospec=True
        ).list_characters = AsyncMock(return_value=[])

        mocker.patch(
            "vbot.cogs.admin.lib.database_handler", autospec=True
        ).update_or_create_campaign = AsyncMock()

        mock_channel_mgr_instance = AsyncMock()
        mock_channel_mgr_instance.messages = []
        mocker.patch(
            "vbot.cogs.admin.lib.ChannelManager",
            return_value=mock_channel_mgr_instance,
        )

        mock_guild = MagicMock()

        # When: running resync
        from vbot.cogs.admin.lib import resync_all_data

        await resync_all_data(user_api_id="user-001", guild=mock_guild)

        # Then: stale records are deleted
        assert await DBCampaign.filter(api_id="c-stale").count() == 0
        assert await DBCampaignBook.filter(api_id="b-stale").count() == 0
        assert await DBCharacter.filter(api_id="char-stale").count() == 0

        # Then: active campaign remains
        assert await DBCampaign.filter(api_id="c-001").count() == 1
