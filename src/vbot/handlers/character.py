"""Handler for character API events."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger
from vclient import characters_service
from vclient.models import CharacterCreate

from vbot.db.models import DBCampaign, DBCharacter
from vbot.lib.channel_mngr import ChannelManager

if TYPE_CHECKING:
    from vclient.constants import CharacterClass, CharacterStatus, CharacterType, GameVersion
    from vclient.models import (
        Character,
        CharacterCreateTraitAssign,
        HunterAttributesCreate,
        HunterAttributesUpdate,
        MageAttributes,
        VampireAttributesCreate,
        VampireAttributesUpdate,
        WerewolfAttributesCreate,
        WerewolfAttributesUpdate,
    )

    from vbot.bot import ValentinaContext

__all__ = ("character_handler",)


class CharacterAPIHandler:
    """Handler for character API events."""

    async def update_or_create_character_in_db(self, character: Character) -> DBCharacter:
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
                "DB: Update or create character in database.",
                name=db_character.name,
                api_id=db_character.api_id,
                status=db_character.status,
            )

        return db_character

    async def list_characters(  # noqa: PLR0913
        self,
        campaign_api_id: str,
        user_api_id: str,
        *,
        user_player_id: str | None = None,
        user_creator_id: str | None = None,
        character_class: CharacterClass | None = None,
        character_type: CharacterType | None = None,
        status: CharacterStatus | None = None,
    ) -> list[Character]:
        """Get all characters as a list.

        Args:
            campaign_api_id (str): The API ID of the campaign.
            user_api_id (str): The API ID of the user performing the action.
            user_player_id (str | None): The API ID of the user who is the player of the character.
            user_creator_id (str | None): The API ID of the user who created the character.
            character_class (CharacterClass | None): The class of the character.
            character_type (CharacterType | None): The type of the character.
            status (CharacterStatus | None): The status of the character.

        Returns:
            list[Character]: The list of characters.
        """
        characters = await characters_service(
            user_id=user_api_id, campaign_id=campaign_api_id
        ).list_all(
            user_player_id=user_player_id or None,
            user_creator_id=user_creator_id or None,
            character_class=character_class or None,
            character_type=character_type or None,
            status=status or None,
        )

        for character in characters:
            await self.update_or_create_character_in_db(character)

        return characters

    async def get_character(
        self, *, user_api_id: str, campaign_api_id: str, character_api_id: str
    ) -> Character:
        """Get a character by ID.

        Args:
            user_api_id (str): The API ID of the user performing the action.
            campaign_api_id (str): The API ID of the campaign.
            character_api_id (str): The API ID of the character.

        Returns:
            Character: The character data transfer object.
        """
        character = await characters_service(user_id=user_api_id, campaign_id=campaign_api_id).get(
            character_api_id
        )

        await self.update_or_create_character_in_db(character)

        return character

    async def create_character(  # noqa: PLR0913
        self,
        ctx: ValentinaContext,
        *,
        campaign_api_id: str,
        age: int | None = None,
        biography: str | None = None,
        character_class: CharacterClass,
        character_type: CharacterType | None = None,
        concept_id: str | None = None,
        demeanor: str | None = None,
        game_version: GameVersion,
        name_first: str,
        name_last: str,
        name_nick: str | None = None,
        nature: str | None = None,
        traits: list[CharacterCreateTraitAssign] | None = None,
        vampire_attributes: VampireAttributesCreate | None = None,
        werewolf_attributes: WerewolfAttributesCreate | None = None,
        hunter_attributes: HunterAttributesCreate | None = None,
        mage_attributes: MageAttributes | None = None,
    ) -> Character:
        """Create a character."""
        user_api_id = await ctx.get_api_user_id()

        request = CharacterCreate(
            name_first=name_first,
            name_last=name_last,
            name_nick=name_nick or None,
            biography=biography or None,
            demeanor=demeanor or None,
            nature=nature or None,
            concept_id=concept_id or None,
            traits=traits or None,
            character_class=character_class,
            game_version=game_version,
            type=character_type or None,
            age=age or None,
            vampire_attributes=vampire_attributes or None,
            werewolf_attributes=werewolf_attributes or None,
            mage_attributes=mage_attributes or None,
            hunter_attributes=hunter_attributes or None,
        )

        character = await characters_service(
            user_id=user_api_id, campaign_id=campaign_api_id
        ).create(request=request)
        await self.update_or_create_character_in_db(character)
        return character

    async def update_character(  # noqa: PLR0913
        self,
        ctx: ValentinaContext,
        *,
        campaign_api_id: str,
        character_api_id: str,
        character_class: CharacterClass | None = None,
        character_type: CharacterType | None = None,
        game_version: GameVersion | None = None,
        status: CharacterStatus | None = None,
        name_first: str | None = None,
        name_last: str | None = None,
        name_nick: str | None = None,
        age: int | None = None,
        biography: str | None = None,
        demeanor: str | None = None,
        nature: str | None = None,
        concept_id: str | None = None,
        user_player_id: str | None = None,
        vampire_attributes: VampireAttributesUpdate | None = None,
        werewolf_attributes: WerewolfAttributesUpdate | None = None,
        mage_attributes: MageAttributes | None = None,
        hunter_attributes: HunterAttributesUpdate | None = None,
    ) -> Character:
        """Patch a character."""
        user_api_id = await ctx.get_api_user_id()

        character = await characters_service(
            user_id=user_api_id, campaign_id=campaign_api_id
        ).update(
            character_api_id,
            character_class=character_class or None,
            character_type=character_type or None,
            game_version=game_version or None,
            status=status or None,
            name_first=name_first or None,
            name_last=name_last or None,
            name_nick=name_nick or None,
            age=age or None,
            biography=biography or None,
            demeanor=demeanor or None,
            nature=nature or None,
            concept_id=concept_id or None,
            user_player_id=user_player_id or None,
            vampire_attributes=vampire_attributes or None,
            werewolf_attributes=werewolf_attributes or None,
            mage_attributes=mage_attributes or None,
            hunter_attributes=hunter_attributes or None,
        )

        db_character = await self.update_or_create_character_in_db(character)

        if name_first or name_last or name_nick or status or character_type:
            db_campaign = await DBCampaign.get_or_none(api_id=campaign_api_id)
            if db_campaign:
                channel_manager = ChannelManager(guild=ctx.guild)
                await channel_manager.confirm_character_channel(
                    character=db_character, campaign=db_character.campaign
                )
                await channel_manager.sort_campaign_channels(db_character.campaign)

        return character

    async def delete_character(
        self,
        ctx: ValentinaContext,
        *,
        user_api_id: str,
        campaign_api_id: str,
        character_api_id: str,
    ) -> None:
        """Delete a character."""
        await characters_service(user_id=user_api_id, campaign_id=campaign_api_id).delete(
            character_api_id
        )

        db_character = await DBCharacter.get_or_none(api_id=character_api_id)
        if db_character:
            channel_manager = ChannelManager(guild=ctx.guild)
            await channel_manager.delete_character_channel(character=db_character)

            await db_character.delete()


character_handler = CharacterAPIHandler()
