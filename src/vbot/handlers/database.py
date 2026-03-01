"""Database handler."""

__all__ = ("DatabaseHandler",)
import discord
from loguru import logger
from vclient.models import Campaign, CampaignBook, Character, User

from vbot.db.models import DBCampaign, DBCampaignBook, DBCharacter, DBUser

__all__ = ("database_handler",)


class DatabaseHandler:
    """Database handler."""

    async def update_or_create_campaign(self, campaign: Campaign) -> DBCampaign:
        """Update or create a campaign in the database.

        Args:
            campaign (Campaign): The campaign data transfer object.

        Returns:
            DBCampaign: The campaign database object.
        """
        db_campaign, created = await DBCampaign.update_or_create(
            api_id=campaign.id,
            defaults={"name": campaign.name},
        )
        if created:
            logger.debug(
                "Create campaign in database.",
                campaign_id=campaign.id,
                campaign_name=campaign.name,
            )

        return db_campaign

    async def update_or_create_book(self, book: CampaignBook) -> DBCampaignBook:
        """Update or create a book in the database.

        Args:
            book (CampaignBook): The book data transfer object.

        Returns:
            DBCampaignBook: The book database object.
        """
        db_campaign = await DBCampaign.get_or_none(api_id=book.campaign_id)
        db_book, created = await DBCampaignBook.update_or_create(
            api_id=book.id,
            defaults={"name": book.name, "number": book.number, "campaign": db_campaign},
        )
        if created:
            logger.debug(
                "Create book in database.",
                book_id=db_book.api_id,
                book_name=book.name,
            )
        return db_book

    async def update_or_create_character(self, character: Character) -> DBCharacter:
        """Update or create a character in the database.

        Args:
            character (Character): The character data transfer object.

        Returns:
            Character: The character database object.
        """
        db_campaign = await DBCampaign.get_or_none(api_id=character.campaign_id)
        db_character, created = await DBCharacter.update_or_create(
            api_id=character.id,
            defaults={
                "name": character.name,
                "campaign": db_campaign,
                "user_player_api_id": character.user_player_id,
                "user_creator_api_id": character.user_creator_id,
                "type": character.type,
                "status": character.status,
            },
        )
        if created:
            logger.debug(
                "Create character in database.",
                name=db_character.name,
                api_id=db_character.api_id,
                status=db_character.status,
            )

        return db_character

    async def update_or_create_user(
        self,
        user: User,
        *,
        discord_user: discord.Member | discord.User,
    ) -> DBUser:
        """Update or create a user in the database.

        Args:
            user (User): The user data transfer object.
            discord_user (discord.Member | discord.User): The Discord user.

        Returns:
            DBUser: The user database object.
        """
        db_user, created = await DBUser.update_or_create(
            discord_user_id=discord_user.id,
            defaults={
                "api_user_id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
            },
        )
        if created:
            logger.debug(
                "Create user in database.",
                username=db_user.username,
                api_id=db_user.api_user_id,
            )

        return db_user

    async def delete_campaign(self, campaign_api_id: str) -> None:
        """Delete a campaign from the database.

        Args:
            campaign_api_id (str): The API ID of the campaign to delete.
        """
        db_campaign = await DBCampaign.get_or_none(api_id=campaign_api_id)
        for book in await DBCampaignBook.filter(campaign=db_campaign):
            await self.delete_book(book.api_id)
            logger.debug(
                "Delete book from database.",
                book_api_id=book.api_id,
            )
        await db_campaign.delete()
        logger.debug(
            "Delete campaign from database.",
            campaign_api_id=campaign_api_id,
        )

    async def delete_book(self, book_api_id: str) -> None:
        """Delete a book from the database.

        Args:
            book_api_id (str): The API ID of the book to delete.
        """
        await DBCampaignBook.filter(api_id=book_api_id).delete()
        logger.debug(
            "Delete book from database.",
            book_api_id=book_api_id,
        )

    async def delete_character(self, character_api_id: str) -> None:
        """Delete a character from the database.

        Args:
            character_api_id (str): The API ID of the character to delete.
        """
        await DBCharacter.filter(api_id=character_api_id).delete()
        logger.debug(
            "Delete character from database.",
            character_api_id=character_api_id,
        )

    async def delete_user(self, discord_user_id: int) -> None:
        """Delete a user from the database.

        Args:
            discord_user_id (int): The ID of the user to delete.
        """
        await DBUser.filter(discord_user_id=discord_user_id).delete()
        logger.debug(
            "Delete user from database.",
            discord_user_id=discord_user_id,
        )


database_handler = DatabaseHandler()
