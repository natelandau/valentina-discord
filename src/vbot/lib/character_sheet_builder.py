"""Controller for displaying a character sheet."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, assert_never

from vclient import character_blueprint_service, character_traits_service

from vbot.constants import EmojiDict

if TYPE_CHECKING:
    import discord
    from vclient.models import (
        Character,
        CharacterConcept,
        CharacterTrait,
        SheetSection,
        TraitCategory,
    )

    from vbot.bot import ValentinaAutocompleteContext, ValentinaContext


@dataclass
class SectionCategoryObject:
    """A list of traits for a specific category."""

    category: TraitCategory
    traits: list[CharacterTrait] = field(default_factory=list)


@dataclass
class SheetSectionObject:
    """A section of the character sheet."""

    section: SheetSection
    categories: list[SectionCategoryObject] = field(default_factory=list)


class CharacterSheetController:
    """Controller for displaying a character sheet."""

    def __init__(
        self,
        *,
        ctx: ValentinaContext | ValentinaAutocompleteContext,
        character: Character,
    ):
        """Initialize the character sheet controller.

        Args:
            ctx (ValentinaContext): The context containing the guild.
            character (dto.CharacterDTO): The character to display.
        """
        self.ctx = ctx
        self.character = character
        self._user_api_id: str = None

    @property
    async def user_api_id(self) -> str:
        """Get the user API ID."""
        if self._user_api_id is None:
            self._user_api_id = await self.ctx.get_api_user_id()
        return self._user_api_id

    async def build_profile(  # noqa: C901
        self,
        *,
        player_discord_member: discord.User | discord.Member | None = None,
        concept_dto: CharacterConcept | None = None,
        storyteller_view: bool = False,
    ) -> dict:
        """Build the profile section for the character sheet.

        Args:
            storyteller_view (bool): Whether to build the profile for a storyteller view.
            concept_dto (dto.CharacterConceptDTO | None): The concept data transfer object.
            player_discord_member (discord.User | discord.Member | None): The Discord member for the player.

        Returns:
            dict: The profile section for the character sheet.
        """
        alive_value = EmojiDict.ALIVE if self.character.status == "ALIVE" else EmojiDict.DEAD

        profile = {
            "class": self.character.character_class.title(),
            "alive": alive_value,
            "concept": concept_dto.name.title() if concept_dto else "-",
            "demeanor": self.character.demeanor.title() if self.character.demeanor else "-",
            "nature": self.character.nature.title() if self.character.nature else "-",
            "age": self.character.age or "",
        }

        match self.character.character_class:
            case "VAMPIRE" | "GHOUL":
                if self.character.vampire_attributes:
                    profile["clan"] = self.character.vampire_attributes.clan_name or "-"
                    profile["generation"] = self.character.vampire_attributes.generation or "-"
                    profile[" sire"] = self.character.vampire_attributes.sire or "-"
            case "WEREWOLF":
                if self.character.werewolf_attributes:
                    profile["tribe"] = self.character.werewolf_attributes.tribe_name or "-"
                    profile["auspice"] = self.character.werewolf_attributes.auspice_name or "-"
                    profile["pack_name"] = self.character.werewolf_attributes.pack_name or "-"
            case "MAGE":
                if self.character.mage_attributes:
                    profile["sphere"] = self.character.mage_attributes.sphere or "-"
                    profile["tradition"] = self.character.mage_attributes.tradition or "-"
            case "HUNTER":
                if self.character.hunter_attributes:
                    profile["creed"] = self.character.hunter_attributes.creed or "-"
            case "MORTAL":
                pass
            case _:
                assert_never(self.character.character_class)

        if player_discord_member:
            profile["player"] = player_discord_member.mention

        if storyteller_view:
            profile["character type"] = (
                "Player Character"
                if self.character.type == "PLAYER"
                else "Storyteller Character"
                if self.character.type == "STORYTELLER"
                else ""
            )

        return {k.title(): str(v) for k, v in profile.items() if v and v != "None"}

    async def build_sheet_traits(self) -> list[SheetSectionObject]:
        """Build the character sheet."""
        # First we find all possible sheet sections
        sections = await character_blueprint_service().list_all_sections(
            game_version=self.character.game_version,
        )
        sheet_section_objects = [SheetSectionObject(section=section) for section in sections]

        # Then we find all possible section categories
        for sheet_section in sheet_section_objects:
            categories = await character_blueprint_service().list_all_categories(
                game_version=self.character.game_version,
                section_id=sheet_section.section.id,
            )
            for category in categories:
                sheet_section.categories.append(SectionCategoryObject(category=category))

        # Then we find all the character's traits and assign them to the appropriate section and category
        character_traits = await character_traits_service(
            user_id=await self.user_api_id,
            campaign_id=self.character.campaign_id,
            character_id=self.character.id,
        ).list_all()

        for sheet_section in sheet_section_objects:
            for section_category in sheet_section.categories:
                section_category.traits = sorted(
                    [
                        trait
                        for trait in character_traits
                        if trait.trait.parent_category_id == section_category.category.id
                        and (trait.value > 0 or trait.trait.show_when_zero)
                    ],
                    key=lambda x: x.trait.name,
                )

        # Then we remove categories and sections that have no traits
        for sheet_section_object in sheet_section_objects:
            sheet_section_object.categories = sorted(
                [
                    category
                    for category in sheet_section_object.categories
                    if category.traits or category.category.show_when_empty
                ],
                key=lambda x: x.category.order,
            )

        return sorted(
            [x for x in sheet_section_objects if x.categories or x.section.show_when_empty],
            key=lambda x: x.section.order,
        )
