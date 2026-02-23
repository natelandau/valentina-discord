"""Handler for campaign API events."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger
from vclient import campaigns_service

from vbot.db.models import DBCampaign
from vbot.lib.channel_mngr import ChannelManager

if TYPE_CHECKING:
    from vclient.models import Campaign

    from vbot.bot import ValentinaContext

__all__ = ("campaign_handler",)


class CampaignAPIHandler:
    """Handler for campaign API events."""

    async def _update_or_create_campaign(self, campaign: Campaign) -> DBCampaign:
        """Update or create a campaign in the database.

        Args:
            campaign (Campaign): The campaign data transfer object.

        Returns:
            Campaign: The campaign database object.
        """
        db_campaign, created = await DBCampaign.update_or_create(
            api_id=campaign.id,
            defaults={"name": campaign.name},
        )
        if created:
            logger.debug(
                "Update or create campaign in database.",
                campaign_id=campaign.id,
                campaign_name=campaign.name,
            )

        return db_campaign

    async def list_campaigns(self, user_api_id: str) -> list[Campaign]:
        """List all campaigns for a user.

        Args:
            user_api_id (str): The API ID of the user.

        Returns:
            list[Campaign]: The list of campaigns.
        """
        campaigns = await campaigns_service(user_id=user_api_id).list_all()
        for campaign in campaigns:
            await self._update_or_create_campaign(campaign)

        return campaigns

    async def get_campaign(self, user_api_id: str, campaign_api_id: str) -> Campaign:
        """Get a campaign by its API ID.

        Args:
            user_api_id (str): The API ID of the user.
            campaign_api_id (str): The API ID of the campaign.

        Returns:
            Campaign: The campaign.
        """
        campaign = await campaigns_service(user_id=user_api_id).get(campaign_api_id)
        await self._update_or_create_campaign(campaign)
        return campaign

    async def create_campaign(
        self,
        ctx: ValentinaContext,
        *,
        name: str,
        description: str | None = None,
        desperation: int = 0,
        danger: int = 0,
    ) -> Campaign:
        """Create a campaign.

        Args:
            ctx (ValentinaContext): The context of the command.
            campaign (Campaign): The campaign.
            name (str): The name of the campaign.
            description (str | None): The description of the campaign.
            desperation (int): The desperation of the campaign.
            danger (int): The danger of the campaign.

        Returns:
            Campaign: The created campaign.
        """
        api_user_id = await ctx.get_api_user_id()
        campaign = await campaigns_service(user_id=api_user_id).create(
            name=name, description=description, desperation=desperation, danger=danger
        )
        db_campaign = await self._update_or_create_campaign(campaign)
        channel_manager = ChannelManager(guild=ctx.guild)
        await channel_manager.confirm_campaign_channels(db_campaign)

        return campaign

    async def update_campaign(
        self,
        ctx: ValentinaContext,
        campaign_api_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        desperation: int | None = None,
        danger: int | None = None,
    ) -> Campaign:
        """Update a campaign.

        Args:
            ctx (ValentinaContext): The context of the command.
            campaign_api_id (str): The API ID of the campaign.
            name (str): The name of the campaign.
            description (str | None): The description of the campaign.
            desperation (int | None): The desperation of the campaign.
            danger (int | None): The danger of the campaign.

        Returns:
            Campaign: The updated campaign.
        """
        api_user_id = await ctx.get_api_user_id()
        campaign = await campaigns_service(user_id=api_user_id).update(
            campaign_api_id,
            name=name or None,
            description=description or None,
            desperation=desperation or None,
            danger=danger or None,
        )
        db_campaign = await self._update_or_create_campaign(campaign=campaign)
        if name:
            channel_manager = ChannelManager(guild=ctx.guild)
            await channel_manager.confirm_campaign_channels(db_campaign)

        return campaign

    async def delete_campaign(self, ctx: ValentinaContext, campaign_api_id: str) -> None:
        """Delete a campaign.

        Args:
            ctx (ValentinaContext): The context of the command.
            campaign_api_id (str): The API ID of the campaign.
        """
        api_user_id = await ctx.get_api_user_id()
        await campaigns_service(user_id=api_user_id).delete(campaign_api_id)

        db_campaign = await DBCampaign.get_or_none(api_id=campaign_api_id)
        if db_campaign:
            channel_manager = ChannelManager(guild=ctx.guild)
            await channel_manager.delete_campaign_channels(db_campaign)
            await db_campaign.delete()

        logger.debug(
            "Delete campaign from database.",
            campaign_api_id=campaign_api_id,
        )


campaign_handler = CampaignAPIHandler()
