"""Manage channels within a Guild."""

import asyncio
from threading import Lock

import discord
from loguru import logger

from vbot.constants import (
    CHANNEL_PERMISSIONS,
    CampaignChannelName,
    ChannelPermission,
    EmojiDict,
)
from vbot.db.models import DBCampaign, DBCampaignBook, DBCharacter

from vbot.utils.discord import set_channel_perms  # isort:skip

CAMPAIGN_COMMON_CHANNELS = {  # channel_db_key: channel_name
    "storyteller_channel_id": CampaignChannelName.STORYTELLER.value,
    "general_channel_id": CampaignChannelName.GENERAL.value,
}

# create lock
LOCK = Lock()


class ChannelManager:  # pragma: no cover
    """Manage channels within a Guild."""

    def __init__(self, guild: discord.Guild):
        self.guild = guild
        self.messages: list[str] = []

    @staticmethod
    def _channel_sort_order(channel: discord.TextChannel) -> tuple[int, str]:  # pragma: no cover
        """Generate a custom sorting key for campaign channels.

        Prioritize channels based on their names, assigning a numeric value for sorting order.

        Args:
            channel (discord.TextChannel): The Discord text channel to generate the sort key for.

        Returns:
            tuple[int, str]: A tuple containing the sort priority (int) and the channel name (str).
        """
        if channel.name.startswith(EmojiDict.CHANNEL_GENERAL):
            return (0, channel.name)

        if channel.name.startswith(EmojiDict.BOOK):
            return (1, channel.name)

        if channel.name.startswith(EmojiDict.CHANNEL_PRIVATE):
            return (2, channel.name)

        if channel.name.startswith(EmojiDict.CHANNEL_PLAYER):
            return (3, channel.name)

        if channel.name.startswith(EmojiDict.CHANNEL_PLAYER_DEAD):
            return (4, channel.name)

        return (5, channel.name)

    async def _remove_unused_campaign_channels(
        self,
        campaign: DBCampaign,
        channels: list[discord.TextChannel],
    ) -> None:
        """Remove any unused campaign channels."""
        await campaign.refresh_from_db()
        await campaign.fetch_related("books", "characters")
        books = await campaign.books.all()
        characters = await campaign.characters.all()

        book_channel_ids = {x.book_channel_id for x in books if x.book_channel_id}
        player_character_channel_ids = {
            x.character_channel_id
            for x in characters
            if x.type == "PLAYER" and x.character_channel_id
        }
        storyteller_character_channel_ids = {
            x.character_channel_id
            for x in characters
            if x.type == "STORYTELLER" and x.character_channel_id
        }

        for channel in channels:
            # Book channels
            if channel.name.startswith(EmojiDict.BOOK) and channel.id not in book_channel_ids:
                logger.info(
                    "Delete unused campaign book channel",
                    campaign_id=campaign.id,
                    campaign_name=campaign.name,
                    channel_id=channel.id,
                    channel_name=channel.name,
                )
                await self.delete_channel(channel)
                await asyncio.sleep(1)
                continue

            # Player character channels
            if (
                channel.name.startswith(EmojiDict.CHANNEL_PLAYER)
                or channel.name.startswith(EmojiDict.CHANNEL_PLAYER_DEAD)
            ) and channel.id not in player_character_channel_ids:
                logger.info(
                    "Delete unused campaign player character channel",
                    campaign_id=campaign.id,
                    campaign_name=campaign.name,
                    channel_id=channel.id,
                    channel_name=channel.name,
                )
                await self.delete_channel(channel)
                await asyncio.sleep(1)
                continue

            # Storyteller character channels
            if (
                channel.name.startswith(f"{EmojiDict.CHANNEL_PRIVATE}{EmojiDict.CHANNEL_PLAYER}")
                or channel.name.startswith(
                    f"{EmojiDict.CHANNEL_PRIVATE}{EmojiDict.CHANNEL_PLAYER_DEAD}"
                )
            ) and channel.id not in storyteller_character_channel_ids:
                logger.info(
                    "Delete unused campaign storyteller character channel",
                    campaign_id=campaign.id,
                    campaign_name=campaign.name,
                    channel_id=channel.id,
                    channel_name=channel.name,
                )
                await self.delete_channel(channel)
                await asyncio.sleep(1)
                continue

            if (
                channel.name.startswith(CampaignChannelName.STORYTELLER.value)
                and channel.id != campaign.storyteller_channel_id
            ):
                logger.info(
                    "Delete unused campaign storyteller channel",
                    campaign_id=campaign.id,
                    campaign_name=campaign.name,
                    channel_id=channel.id,
                    channel_name=channel.name,
                )
                await self.delete_channel(channel)
                await asyncio.sleep(1)
                continue

            if (
                channel.name.startswith(CampaignChannelName.GENERAL.value)
                and channel.id != campaign.general_channel_id
            ):
                logger.info(
                    "Delete unused campaign general channel",
                    campaign_id=campaign.id,
                    campaign_name=campaign.name,
                    channel_id=channel.id,
                    channel_name=channel.name,
                )
                await self.delete_channel(channel)
                await asyncio.sleep(1)
                continue

    async def _confirm_campaign_common_channels(
        self,
        *,
        campaign: DBCampaign,
        category: discord.CategoryChannel,
        channels: list[discord.TextChannel],
    ) -> None:
        """Ensure common campaign channels exist and are up-to-date.

        This method checks for the existence of common campaign channels within the specified category. If a channel does not exist, it creates it. If a channel exists but its ID does not match the database, it updates the database with the correct ID.

        Args:
            campaign (DBCampaign): The campaign object containing channel information.
            category (discord.CategoryChannel): The category under which the channels should exist.
            channels (list[discord.TextChannel]): The list of existing channels in the category.
        """
        for channel_db_key, channel_name in CAMPAIGN_COMMON_CHANNELS.items():
            await asyncio.sleep(1)  # Keep the rate limit happy

            channel_db_id = getattr(campaign, channel_db_key, None)

            channel = await self.confirm_channel_in_category(
                existing_category=category,
                existing_channels=channels,
                channel_name=channel_name,
                channel_db_id=channel_db_id,
            )

            if not channel_db_id or channel_db_id != channel.id:
                await DBCampaign.filter(id=campaign.id).update(**{channel_db_key: channel.id})

    def _determine_channel_permissions(
        self,
        channel_name: str,
    ) -> tuple[ChannelPermission, ChannelPermission, ChannelPermission]:
        """Determine the permissions for the specified channel based on its name.

        Args:
            channel_name (str): The name of the channel to determine permissions for.

        Returns:
            tuple[ChannelPermission, ChannelPermission, ChannelPermission]: A tuple containing:
                - The default role permissions (ChannelPermission)
                - The player role permissions (ChannelPermission)
                - The storyteller role permissions (ChannelPermission)
        """
        if channel_name.startswith(EmojiDict.CHANNEL_PRIVATE):
            return CHANNEL_PERMISSIONS["storyteller_channel"]

        if channel_name.startswith((EmojiDict.CHANNEL_PLAYER, EmojiDict.CHANNEL_PLAYER_DEAD)):
            return CHANNEL_PERMISSIONS["campaign_character_channel"]

        return CHANNEL_PERMISSIONS["default"]

    async def confirm_channel_in_category(
        self,
        existing_category: discord.CategoryChannel,
        existing_channels: list[discord.TextChannel],
        channel_name: str,
        channel_db_id: int | None = None,
        owned_by_user: discord.User | discord.Member | None = None,
        topic: str | None = None,
    ) -> discord.TextChannel:
        """Confirm the channel exists in the category.

        Confirm that the channel exists within the category. If the channel does not exist, create it.

        Args:
            existing_category (discord.CategoryChannel): The category to check for the channel in.
            existing_channels (list[discord.TextChannel]): The list of channels existing in the category.
            channel_name (str): The name of the channel to check for.
            channel_db_id (optional, int): The ID of the channel in the database.
            owned_by_user (discord.User | discord.Member, optional): The user who owns the channel. Defaults to None.
            topic (str, optional): The topic description for the channel. Defaults to None.

        Returns:
            discord.TextChannel: The channel object.
        """
        channel_name_is_in_category = any(
            channel_name == channel.name for channel in existing_channels
        )
        channel_db_id_is_in_category = (
            any(channel_db_id == channel.id for channel in existing_channels)
            if channel_db_id
            else False
        )

        # If the channel exists in the category, return it
        if channel_name_is_in_category:
            await asyncio.sleep(1)  # Keep the rate limit happy
            preexisting_channel = next(
                (channel for channel in existing_channels if channel.name == channel_name),
                None,
            )
            # update channel permissions
            await asyncio.sleep(1)  # Keep the rate limit happy
            return await self.channel_update_or_add(
                channel=preexisting_channel,
                name=channel_name,
                category=existing_category,
                permissions=self._determine_channel_permissions(channel_name),
                permissions_user_post=owned_by_user,
                topic=topic,
            )

        # If the channel id exists but the name is different, rename the existing channel
        if channel_db_id and channel_db_id_is_in_category and not channel_name_is_in_category:
            existing_channel_object = next(
                (channel for channel in existing_channels if channel_db_id == channel.id),
                None,
            )
            logger.info(
                "Channel exists in database and category but name is different. Renamed channel.",
                channel_name=channel_name,
                existing_category=existing_category.name,
                channel_db_id=channel_db_id,
            )

            await asyncio.sleep(1)  # Keep the rate limit happy
            return await self.channel_update_or_add(
                channel=existing_channel_object,
                name=channel_name,
                category=existing_category,
                permissions=self._determine_channel_permissions(channel_name),
                permissions_user_post=owned_by_user,
                topic=topic,
            )

        # Finally, if the channel does not exist in the category, create it

        await asyncio.sleep(1)  # Keep the rate limit happy
        logger.info(
            "Channel does not exist in category. Create channel.",
            channel_name=channel_name,
            existing_category_name=existing_category.name,
            existing_category_id=existing_category.id,
        )
        await asyncio.sleep(1)  # Keep the rate limit happy

        return await self.channel_update_or_add(
            name=channel_name,
            category=existing_category,
            permissions=self._determine_channel_permissions(channel_name),
            permissions_user_post=owned_by_user,
            topic=topic,
        )

    async def channel_update_or_add(
        self,
        permissions: tuple[ChannelPermission, ChannelPermission, ChannelPermission],
        channel: discord.TextChannel | None = None,
        name: str | None = None,
        topic: str | None = None,
        category: discord.CategoryChannel | None = None,
        permissions_user_post: discord.User | discord.Member | None = None,
    ) -> discord.TextChannel:  # pragma: no cover
        """Create or update a channel in the guild with specified permissions and attributes.

        Create a new text channel or update an existing one based on the provided name. Set permissions for default role, player role, and storyteller role. Automatically grant manage permissions to bot members. If specified, set posting permissions for a specific user.

        Args:
            permissions (tuple[ChannelPermission, ChannelPermission, ChannelPermission]): Permissions for default role, player role, and storyteller role respectively.
            channel (discord.TextChannel, optional): Existing channel to update. Defaults to None.
            name (str, optional): Name for the channel. Defaults to None.
            topic (str, optional): Topic description for the channel. Defaults to None.
            category (discord.CategoryChannel, optional): Category to place the channel in. Defaults to None.
            permissions_user_post (discord.User | discord.Member, optional): User to grant posting permissions. Defaults to None.

        Returns:
            discord.TextChannel: The newly created or updated text channel.
        """
        # Fetch roles from the guild
        player_role = discord.utils.get(self.guild.roles, name="Player")
        storyteller_role = discord.utils.get(self.guild.roles, name="Storyteller")

        # Initialize permission overwrites. Always grant manage permissions to bots.
        overwrites = {  # type: ignore[misc]
            self.guild.default_role: set_channel_perms(permissions[0]),
            player_role: set_channel_perms(permissions[1]),
            storyteller_role: set_channel_perms(permissions[2]),
            **{
                user: set_channel_perms(ChannelPermission.MANAGE)
                for user in self.guild.members
                if user.bot
            },
        }

        if permissions_user_post:
            overwrites[permissions_user_post] = set_channel_perms(ChannelPermission.POST)

        formatted_name = name.lower().strip().replace(" ", "-") if name else None

        if name and not channel:
            for existing_channel in self.guild.text_channels:
                # If channel already exists in a specified category, edit it
                if (
                    category
                    and existing_channel.category == category
                    and existing_channel.name == formatted_name
                ) or (not category and existing_channel.name == formatted_name):
                    logger.debug(
                        "Update channel",
                        channel_name=formatted_name,
                        guild_name=self.guild.name,
                        category=category.name if category else None,
                        existing_channel=existing_channel.name if existing_channel else None,
                    )
                    await existing_channel.edit(
                        name=formatted_name,
                        overwrites=overwrites,
                        topic=topic or existing_channel.topic,
                        category=category or existing_channel.category,
                    )
                    return existing_channel

            # Create the channel if it doesn't exist
            logger.debug(
                "Create channel",
                channel_name=formatted_name,
                guild_name=self.guild.name,
                category=category.name if category else None,
            )
            return await self.guild.create_text_channel(
                name=formatted_name, overwrites=overwrites, topic=topic, category=category
            )

        # Update existing channel
        logger.debug(
            "Update channel",
            channel_name=channel.name,
            guild_name=self.guild.name,
            category=category.name if category else None,
        )
        await channel.edit(
            name=name or channel.name,
            overwrites=overwrites,
            topic=topic or channel.topic,
            category=category or channel.category,
        )

        return channel

    async def confirm_book_channel(
        self,
        book: DBCampaignBook,
        campaign: DBCampaign | None = None,
    ) -> discord.TextChannel | None:
        """Confirm and retrieve the Discord text channel associated with a given campaign book.

        This method ensures that the specified campaign book has an associated text channel within the campaign's category. If the campaign is not provided, it fetches the campaign using the book's campaign ID. It then verifies the existence of the campaign's category and channels, creating or confirming the required text channel for the book.

        Args:
            book (DBCampaignBook): The campaign book for which the text channel is to be confirmed.
            campaign (Optional[DBCampaign]): The campaign associated with the book. If not provided, it will be fetched from the database.

        Returns:
            discord.TextChannel | None: The confirmed or newly created Discord text channel for the book, or None if the campaign category does not exist.
        """
        logger.debug(
            "Confirming channel for book",
            campaign_id=campaign.id,
            campaign_name=campaign.name,
            book_number=book.number,
            book_name=book.name,
        )
        if not campaign:
            campaign = await book.campaign

        category, channels = await self.fetch_campaign_category_channels(campaign=campaign)

        # If the campaign category channel does not exist, return None
        if not category:
            return None

        channel_db_id = book.book_channel_id

        channel = await self.confirm_channel_in_category(
            existing_category=category,
            existing_channels=channels,
            channel_name=book.get_channel_name(),
            channel_db_id=channel_db_id,
            topic=f"Channel for book {book.number}. {book.name}",
        )
        book.book_channel_id = channel.id
        await book.save()
        await asyncio.sleep(1)  # Keep the rate limit happy
        return channel

    async def confirm_campaign_channels(self, campaign: DBCampaign) -> None:
        """Confirm and manage the channels for a given campaign.

        This method ensures that the necessary category and channels for the campaign exist,
        are correctly named, and are recorded in the database.

        Args:
            campaign (DBCampaign): The campaign object containing details about the campaign.
        """
        global LOCK  # noqa: PLW0602

        # Use a lock to prevent race conditions when multiple instances try to modify channels simultaneously
        with LOCK:
            # Format category name with emoji prefix for visual organization in Discord sidebar
            campaign_category_channel_name = campaign.get_category_channel_name()

            if campaign.category_channel_id:
                existing_campaign_channel_object = self.guild.get_channel(
                    campaign.category_channel_id,
                )

                # Handle case where channel ID exists in DB but channel was deleted from Discord
                if not existing_campaign_channel_object:
                    category = await self.guild.create_category(campaign_category_channel_name)
                    campaign.category_channel_id = category.id
                    await campaign.save()
                    logger.debug(
                        "Campaign category created",
                        campaign_id=campaign.id,
                        campaign_name=campaign.name,
                        campaign_category_channel_name=campaign_category_channel_name,
                        guild_name=self.guild.name,
                    )

                # Update channel name if it was manually changed in Discord or in the API
                elif existing_campaign_channel_object.name != campaign_category_channel_name:
                    await existing_campaign_channel_object.edit(name=campaign_category_channel_name)
                    logger.debug(
                        "Campaign category renamed",
                        campaign_id=campaign.id,
                        campaign_name=campaign.name,
                        campaign_category_channel_name=campaign_category_channel_name,
                        guild_name=self.guild.name,
                    )

            else:
                # Create initial category if this is a new campaign
                category = await self.guild.create_category(campaign_category_channel_name)

                campaign.category_channel_id = category.id
                await campaign.save()

                logger.debug(
                    "Campaign category created",
                    campaign_id=campaign.id,
                    campaign_name=campaign.name,
                    campaign_category_channel_name=campaign_category_channel_name,
                    guild_name=self.guild.name,
                )

            category, channels = await self.fetch_campaign_category_channels(campaign=campaign)

            # Set up standard channels needed for every campaign
            await self._confirm_campaign_common_channels(
                campaign=campaign,
                category=category,
                channels=channels,
            )

            # Fetch the related items from the database
            await campaign.refresh_from_db()
            await campaign.fetch_related("books", "characters")
            books = await campaign.books.all()
            characters = await campaign.characters.all()

            # Add 1 second delay between channel operations to avoid Discord rate limits
            for book in books:
                await self.confirm_book_channel(book=book, campaign=campaign)
                await asyncio.sleep(1)

            for character in [x for x in characters if x.type == "PLAYER"]:
                await self.confirm_character_channel(character=character, campaign=campaign)
                await asyncio.sleep(1)

            for character in [x for x in characters if x.type == "STORYTELLER"]:
                await self.confirm_character_channel(character=character, campaign=campaign)
                await asyncio.sleep(1)

            # Clean up any orphaned channels that are no longer associated with books/characters
            await self._remove_unused_campaign_channels(campaign=campaign, channels=channels)

            # Maintain consistent channel ordering for better navigation
            await self.sort_campaign_channels(campaign=campaign)

            logger.info(
                "All channels confirmed for campaign",
                campaign_id=campaign.id,
                campaign_name=campaign.name,
                guild_name=self.guild.name,
            )

    async def confirm_character_channel(
        self,
        character: DBCharacter,
        campaign: DBCampaign | None,
    ) -> discord.TextChannel | None:
        """Confirm the existence of a character-specific text channel within a campaign category.

        This method checks if a text channel for a given character exists within the specified campaign's category. If the campaign or category does not exist, it returns None. Otherwise, it ensures the channel exists, updates the character's channel ID, and returns the channel.

        Args:
            character (DBCharacter): The character for whom the channel is being confirmed.
            campaign (Optional[DBCampaign]): The campaign within which to confirm the character's channel. If not provided, it will be fetched from the database.

        Returns:
            discord.TextChannel | None: The confirmed text channel for the character, or None if the campaign or category does not exist.
        """
        logger.debug(
            "Confirming channel for character",
            character_id=character.id,
            character_name=character.name,
            campaign_id=campaign.id,
            campaign_name=campaign.name,
        )

        if not campaign:
            campaign = await DBCharacter.campaign

        category, channels = await self.fetch_campaign_category_channels(campaign=campaign)

        # If the campaign category channel does not exist, return None
        if not category:
            return None

        user_player_discord_id = await character.get_user_player_discord_id()
        if not user_player_discord_id:
            self.messages.append(
                f"The player for {character.name} is not associated with a discord user. No channel created."
            )
            return None

        owned_by_user = discord.utils.get(self.guild.members, id=user_player_discord_id)
        channel_name = character.get_channel_name()
        channel_db_id = character.character_channel_id

        channel = await self.confirm_channel_in_category(
            existing_category=category,
            existing_channels=channels,
            channel_name=channel_name,
            channel_db_id=channel_db_id,
            owned_by_user=owned_by_user,
            topic=f"Character channel for {character.name}",
        )
        character.character_channel_id = channel.id
        await character.save()

        await asyncio.sleep(1)  # Keep the rate limit happy
        return channel

    async def delete_book_channel(self, book: DBCampaignBook) -> None:
        """Delete the Discord channel associated with the given book.

        Args:
            book (DBCampaignBook): The book object containing the channel information.
        """
        if not book.book_channel_id:
            return

        channel = self.guild.get_channel(book.book_channel_id)
        if channel:
            await self.delete_channel(channel)

        book.book_channel_id = None
        await book.save()

    async def delete_channel_by_id(self, channel_id: int) -> None:
        """Delete a channel from the guild.

        Args:
            channel_id (int): The ID of the channel to delete.
        """
        channel = self.guild.get_channel(channel_id)
        if channel:
            await self.delete_channel(channel)

    async def delete_campaign_channels(self, campaign: DBCampaign) -> None:
        """Delete all Discord channels associated with the given campaign.

        Args:
            campaign (DBCampaign): The campaign object whose channels are to be deleted.
        """
        logger.debug(
            "Deleting campaign channels for campaign",
            campaign_id=campaign.id,
            campaign_name=campaign.name,
        )

        for book in await campaign.books.all():
            await self.delete_book_channel(book)

        for character in [x for x in await campaign.characters.all() if x.type == "PLAYER"]:
            await self.delete_character_channel(character)

        for character in [x for x in await campaign.characters.all() if x.type == "STORYTELLER"]:
            await self.delete_character_channel(character)

        for channel_db_key in CAMPAIGN_COMMON_CHANNELS:
            if getattr(campaign, channel_db_key, None):
                await self.delete_channel(getattr(campaign, channel_db_key))
                setattr(campaign, channel_db_key, None)
                await campaign.save()
                await asyncio.sleep(1)  # Keep the rate limit happy

        if campaign.category_channel_id:
            await self.delete_channel(campaign.category_channel_id)
            campaign.category_channel_id = None
            await campaign.save()
            await asyncio.sleep(1)

    async def delete_channel(
        self,
        channel: discord.TextChannel
        | discord.CategoryChannel
        | discord.VoiceChannel
        | discord.ForumChannel
        | discord.StageChannel
        | int,
    ) -> None:
        """Delete a specified channel from the guild.

        This method deletes a given channel from the guild. The channel can be specified
        as a discord.TextChannel, discord.CategoryChannel, discord.VoiceChannel,
        discord.ForumChannel, discord.StageChannel, or an integer representing the channel ID.

        Args:
            channel (discord.TextChannel | int): The channel to delete.
        """
        if isinstance(channel, int):
            channel = self.guild.get_channel(channel)

        if not channel:
            return

        logger.debug(
            "Delete channel",
            channel_name=channel.name,
            guild_name=self.guild.name,
        )
        await channel.delete()
        await asyncio.sleep(1)  # Keep the rate limit happy

    async def delete_character_channel(self, character: DBCharacter) -> None:
        """Delete the channel associated with the character.

        Args:
            character (DBCharacter): The character object containing the channel information.
        """
        if not character.character_channel_id:
            return

        channel = self.guild.get_channel(character.character_channel_id)
        if channel:
            await self.delete_channel(channel)

        character.character_channel_id = None
        await character.save()

    async def fetch_campaign_category_channels(
        self,
        campaign: DBCampaign,
    ) -> tuple[discord.CategoryChannel, list[discord.TextChannel]]:
        """Fetch the campaign's channels in the guild.

        Retrieve the category channel and its child text channels for the current campaign
        from the Discord guild.

        Args:
            campaign (DBCampaign): The campaign to fetch the channels for.

        Returns:
            tuple[discord.CategoryChannel, list[discord.TextChannel]]: A tuple containing:
                - The campaign category channel (discord.CategoryChannel or None if not found)
                - A list of text channels within that category (empty list if category not found)
        """
        for category, channels in self.guild.by_category():
            if category and category.id == campaign.category_channel_id:
                return category, [x for x in channels if isinstance(x, discord.TextChannel)]

        return None, []

    async def sort_campaign_channels(self, campaign: DBCampaign) -> None:
        """Sort the campaign's channels within its category.

        This method sorts the channels within the campaign's category based on a custom sorting order.
        It ensures that the channels are positioned correctly according to the defined sort order.

        Args:
            campaign (DBCampaign): The campaign object containing details about the campaign.
        """
        logger.debug(
            "Sort campaign channels",
            campaign_id=campaign.id,
            campaign_name=campaign.name,
            guild_name=self.guild.name,
        )
        for category, channels in self.guild.by_category():
            if category and category.id == campaign.category_channel_id:
                sorted_channels = sorted(channels, key=self._channel_sort_order)  # type: ignore[arg-type]
                for i, channel in enumerate(sorted_channels):
                    if channel.position and channel.position == i:
                        continue
                    await channel.edit(position=i)
                    await asyncio.sleep(2)  # Keep the rate limit happy
                break
