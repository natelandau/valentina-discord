"""Tests for the campaign API handler."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tests.factories import make_campaign
from vbot.db.models import DBCampaign
from vbot.handlers.campaign import campaign_handler

pytestmark = pytest.mark.anyio


class TestListCampaigns:
    """Tests for CampaignAPIHandler.list_campaigns()."""

    async def test_returns_campaigns(self, db, mock_campaigns_service):
        """Verify delegates to API and syncs campaigns to DB."""
        # Given: the API returns two campaigns
        campaigns = [
            make_campaign(id="c-001", name="Alpha"),
            make_campaign(id="c-002", name="Beta"),
        ]
        mock_campaigns_service._service.list_all.return_value = campaigns

        # When: listing campaigns
        result = await campaign_handler.list_campaigns(user_api_id="user-001")

        # Then: the API was called and results returned
        mock_campaigns_service.assert_called_once_with(user_id="user-001")
        mock_campaigns_service._service.list_all.assert_awaited_once()
        assert len(result) == 2

        # Then: campaigns are synced to DB
        assert await DBCampaign.filter(api_id="c-001").count() == 1
        assert await DBCampaign.filter(api_id="c-002").count() == 1

    async def test_empty_list(self, db, mock_campaigns_service):
        """Verify handles empty campaign list gracefully."""
        # Given: the API returns no campaigns
        mock_campaigns_service._service.list_all.return_value = []

        # When: listing campaigns
        result = await campaign_handler.list_campaigns(user_api_id="user-001")

        # Then: empty list returned
        assert result == []


class TestGetCampaign:
    """Tests for CampaignAPIHandler.get_campaign()."""

    async def test_returns_campaign(self, db, mock_campaigns_service):
        """Verify delegates to API and syncs campaign to DB."""
        # Given: the API returns a campaign
        campaign = make_campaign(id="c-001", name="Test Campaign")
        mock_campaigns_service._service.get.return_value = campaign

        # When: getting a campaign
        result = await campaign_handler.get_campaign(
            user_api_id="user-001", campaign_api_id="c-001"
        )

        # Then: the API was called correctly
        mock_campaigns_service.assert_called_once_with(user_id="user-001")
        mock_campaigns_service._service.get.assert_awaited_once_with("c-001")
        assert result.name == "Test Campaign"

        # Then: campaign is synced to DB
        assert await DBCampaign.filter(api_id="c-001").count() == 1


class TestCreateCampaign:
    """Tests for CampaignAPIHandler.create_campaign()."""

    async def test_creates_campaign(self, db, mock_campaigns_service, mock_valentina_context):
        """Verify API called, DB synced, and channel manager invoked."""
        # Given: the API returns a created campaign
        campaign = make_campaign(id="c-001", name="New Campaign")
        mock_campaigns_service._service.create.return_value = campaign

        # Given: channel manager is mocked
        mock_cm = AsyncMock()
        mock_valentina_context.guild = AsyncMock()

        # When: creating a campaign
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "vbot.handlers.campaign.ChannelManager",
                lambda guild: mock_cm,
            )
            result = await campaign_handler.create_campaign(
                mock_valentina_context,
                name="New Campaign",
                description="A new campaign",
                desperation=1,
                danger=2,
            )

        # Then: ctx.get_api_user_id() was called
        mock_valentina_context.get_api_user_id.assert_awaited_once()

        # Then: API was called with correct args
        mock_campaigns_service._service.create.assert_awaited_once_with(
            name="New Campaign", description="A new campaign", desperation=1, danger=2
        )

        # Then: campaign is synced to DB
        assert await DBCampaign.filter(api_id="c-001").count() == 1

        # Then: channel manager was invoked
        mock_cm.confirm_campaign_channels.assert_awaited_once()
        assert result.name == "New Campaign"


class TestUpdateCampaign:
    """Tests for CampaignAPIHandler.update_campaign()."""

    async def test_updates_campaign_with_rename(
        self, db, mock_campaigns_service, mock_valentina_context
    ):
        """Verify API called, DB updated, and channel manager called on rename."""
        # Given: the API returns an updated campaign
        campaign = make_campaign(id="c-001", name="Renamed")
        mock_campaigns_service._service.update.return_value = campaign

        # Given: channel manager is mocked
        mock_cm = AsyncMock()

        # When: updating with a new name
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "vbot.handlers.campaign.ChannelManager",
                lambda guild: mock_cm,
            )
            result = await campaign_handler.update_campaign(
                mock_valentina_context,
                "c-001",
                name="Renamed",
            )

        # Then: API was called
        mock_campaigns_service._service.update.assert_awaited_once_with(
            "c-001", name="Renamed", description=None, desperation=None, danger=None
        )

        # Then: channel manager was invoked for rename
        mock_cm.confirm_campaign_channels.assert_awaited_once()
        assert result.name == "Renamed"

    async def test_updates_campaign_no_rename(
        self, db, mock_campaigns_service, mock_valentina_context
    ):
        """Verify channel manager NOT called when name is unchanged."""
        # Given: the API returns an updated campaign
        campaign = make_campaign(id="c-001", name="Same Name")
        mock_campaigns_service._service.update.return_value = campaign

        # Given: channel manager is mocked
        mock_cm = AsyncMock()

        # When: updating without a name change
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "vbot.handlers.campaign.ChannelManager",
                lambda guild: mock_cm,
            )
            result = await campaign_handler.update_campaign(
                mock_valentina_context,
                "c-001",
                description="Updated desc",
            )

        # Then: channel manager was NOT invoked
        mock_cm.confirm_campaign_channels.assert_not_awaited()
        assert result.name == "Same Name"


class TestDeleteCampaign:
    """Tests for CampaignAPIHandler.delete_campaign()."""

    async def test_deletes_campaign(self, db, mock_campaigns_service, mock_valentina_context):
        """Verify API called, DB record deleted, and channels cleaned up."""
        # Given: a campaign exists in the DB
        await DBCampaign.create(api_id="c-001", name="Doomed Campaign")

        # Given: channel manager is mocked
        mock_cm = AsyncMock()

        # When: deleting the campaign
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "vbot.handlers.campaign.ChannelManager",
                lambda guild: mock_cm,
            )
            await campaign_handler.delete_campaign(mock_valentina_context, "c-001")

        # Then: API delete was called
        mock_campaigns_service._service.delete.assert_awaited_once_with("c-001")

        # Then: DB record is removed
        assert await DBCampaign.filter(api_id="c-001").count() == 0

        # Then: channel manager cleaned up channels
        mock_cm.delete_campaign_channels.assert_awaited_once()

    async def test_deletes_campaign_not_in_db(
        self, db, mock_campaigns_service, mock_valentina_context
    ):
        """Verify handles missing DB record gracefully."""
        # Given: no campaign exists in the DB

        # When: deleting the campaign
        await campaign_handler.delete_campaign(mock_valentina_context, "c-nonexistent")

        # Then: API delete was still called
        mock_campaigns_service._service.delete.assert_awaited_once_with("c-nonexistent")

        # Then: no error raised (graceful handling)
