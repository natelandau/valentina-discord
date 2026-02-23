"""Handler for quick generation of storyteller characters."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from loguru import logger
from vclient import (
    character_autogen_service,
    character_blueprint_service,
    characters_service,
    options_service,
)

from vbot.constants import EmojiDict
from vbot.db.models import DBCampaign, DBCharacter
from vbot.handlers import character_handler
from vbot.lib.channel_mngr import ChannelManager
from vbot.lib.exceptions import CancellationActionError
from vbot.utils.strings import truncate_string
from vbot.views import ConfirmCancelButtons, SelectMenu, SelectMenuView

from .character_sheet import first_page_of_character_sheet_as_embed

if TYPE_CHECKING:
    from vclient.constants import (
        AbilityFocus,
        AutoGenExperienceLevel,
        CharacterClass,
        CharacterType,
        GameVersion,
    )
    from vclient.models import (
        Character,
    )

    from vbot.bot import ValentinaContext


class QuickCharacterGenerationHandler:
    """Handler for quick generation of characters."""

    def __init__(
        self,
        ctx: ValentinaContext,
        db_campaign: DBCampaign,
        api_user_id: str,
        character_type: CharacterType = "STORYTELLER",
    ):
        self.ctx = ctx
        self.db_campaign = db_campaign
        self.api_user_id = api_user_id
        self.character_type: CharacterType = character_type
        self.api_options: dict[str, dict[str, list[str] | dict[str, str]]] | None = None
        self.cancelled = False
        self.character: Character | None = None

        self.game_version: GameVersion = "V5"
        self.character_class: CharacterClass | None = None
        self.concept_id: str | None = None
        self.ability_focus: AbilityFocus | None = None
        self.experience_level: AutoGenExperienceLevel | None = None
        self.vampire_clan_id: str | None = None
        self.werewolf_tribe_id: str | None = None
        self.werewolf_auspice_id: str | None = None

    async def _cancel_character_generation(
        self,
        *,
        msg: str | None = None,
        delete_character: bool = False,
    ) -> None:
        """Cancel the character generation process and clean up resources.

        This method handles the cancellation of character generation, deleting any partially
        created characters and displaying a cancellation message to the user.

        Args:
            msg (str | None): Custom message to display upon cancellation. If None, a default message is used.
            delete_character (bool): Whether to delete the character if it was created.
        """
        self.cancelled = True
        if not msg:
            msg = "No character was created."

        if delete_character and self.character and self.character.id:
            await characters_service(
                user_id=self.api_user_id,
                campaign_id=self.db_campaign.api_id,
            ).delete(self.character.id)

        if isinstance(self.interaction, discord.Interaction):
            await self.interaction.delete_original_response()
        else:
            await self.interaction.delete()

        msg = "Character generation cancelled. No character was created."
        raise CancellationActionError(msg)

    async def start(self) -> None:
        """Guide the user through the quick character generation wizard."""
        self.api_options = await options_service().get_options()
        await self._select_character_options()
        if self.character_class in ["VAMPIRE", "GHOUL"]:
            await self._select_clan()
        if self.character_class == "WEREWOLF":
            await self._select_tribe_auspice()

        self.character = await character_autogen_service(
            user_id=self.api_user_id, campaign_id=self.db_campaign.api_id
        ).generate_character(
            character_class=self.character_class,
            concept_id=self.concept_id,
            skill_focus=self.ability_focus,
            experience_level=self.experience_level,
            vampire_clan_id=self.vampire_clan_id,
            werewolf_tribe_id=self.werewolf_tribe_id,
            werewolf_auspice_id=self.werewolf_auspice_id,
            character_type=self.character_type,
        )

        await self._display_character_sheet()
        await character_handler.update_or_create_character_in_db(self.character)
        await self._update_channels()

    async def _select_character_options(self) -> None:
        """Select the character options from the user."""
        random_option = discord.SelectOption(
            label=" Random",
            value="NONE",
            emoji=EmojiDict.SPARKLES,
        )

        class_menu = SelectMenu(
            placeholder="Choose a character class",
            custom_id="character_class",
            options=[random_option]
            + [
                discord.SelectOption(
                    label=character_class.title(),
                    value=character_class,
                    emoji=getattr(EmojiDict, character_class.upper()),
                )
                for character_class in self.api_options["characters"]["CharacterClass"]
            ],
        )
        concept_menu = SelectMenu(
            placeholder="Choose a concept",
            custom_id="concept_id",
            options=[random_option]
            + [
                discord.SelectOption(
                    label=concept.name,
                    value=concept.id,
                    description=truncate_string(concept.description, 100),
                    emoji=getattr(
                        EmojiDict, concept.name.upper().replace("-", "_"), EmojiDict.OTHER
                    ),
                )
                for concept in await character_blueprint_service().list_all_concepts()
            ],
        )
        ability_focus_menu = SelectMenu(
            placeholder="Choose an Ability Focus",
            custom_id="ability_focus",
            options=[random_option]
            + [
                discord.SelectOption(
                    label=ability_focus.title(),
                    value=ability_focus,
                    emoji=getattr(EmojiDict, ability_focus.upper()),
                )
                for ability_focus in self.api_options["characters"]["AbilityFocus"]
            ],
        )
        experience_level_menu = SelectMenu(
            placeholder="Choose an Experience Level",
            custom_id="experience_level",
            options=[random_option]
            + [
                discord.SelectOption(
                    label=experience.title(),
                    value=experience,
                    emoji=getattr(EmojiDict, experience.upper()),
                )
                for experience in self.api_options["characters"]["AutoGenExperienceLevel"]
            ],
        )

        menu_view = SelectMenuView(
            select_menus=[
                class_menu,
                concept_menu,
                ability_focus_menu,
                experience_level_menu,
            ],
            author=self.ctx.author,
        )
        self.interaction = await self.ctx.respond(
            "Choose your character options! Or keep it random.",
            view=menu_view,
            ephemeral=True,
        )
        await menu_view.wait()
        if menu_view.cancelled:
            await self._cancel_character_generation()

        self.character_class = (
            None  # type: ignore [assignment]
            if menu_view.selections["character_class"] == "NONE"
            else menu_view.selections["character_class"]
        )
        self.concept_id = (
            None
            if menu_view.selections["concept_id"] == "NONE"
            else menu_view.selections["concept_id"]
        )
        self.ability_focus = (
            None  # type: ignore [assignment]
            if menu_view.selections["ability_focus"] == "NONE"
            else menu_view.selections["ability_focus"]
        )
        self.experience_level = (
            None  # type: ignore [assignment]
            if menu_view.selections["experience_level"] == "NONE"
            else menu_view.selections["experience_level"]
        )

    async def _select_clan(self) -> None:
        """Get the clan from the user."""
        clans = await character_blueprint_service().list_all_vampire_clans(
            game_version=self.game_version
        )

        random_option = discord.SelectOption(
            label=" Random",
            value="NONE",
            emoji=EmojiDict.SPARKLES,
        )

        clan_menus = [
            SelectMenu(
                placeholder="Choose a clan",
                custom_id="clan_id",
                options=[random_option]
                + [
                    discord.SelectOption(
                        label=clan.name,
                        value=clan.id,
                        description=truncate_string(clan.description, 100)
                        if clan.description
                        else None,
                    )
                    for clan in clans
                ],
            ),
        ]
        clan_view = SelectMenuView(select_menus=clan_menus, author=self.ctx.author)
        await self.interaction.edit(content="Choose a clan!", view=clan_view)

        await clan_view.wait()
        if clan_view.cancelled:
            await self._cancel_character_generation()

        self.vampire_clan_id = (
            None if clan_view.selections["clan_id"] == "NONE" else clan_view.selections["clan_id"]
        )

    async def _select_tribe_auspice(self) -> None:
        """Get the tribe and auspice from the user."""
        tribes = await character_blueprint_service().list_all_werewolf_tribes(
            game_version=self.game_version
        )
        auspices = await character_blueprint_service().list_all_werewolf_auspices(
            game_version=self.game_version
        )

        random_option = discord.SelectOption(
            label=" Random",
            value="NONE",
            emoji=EmojiDict.SPARKLES,
        )

        tribe_auspice_menus = [
            SelectMenu(
                placeholder="Choose a tribe",
                custom_id="tribe_id",
                options=[random_option]
                + [
                    discord.SelectOption(
                        label=tribe.name,
                        value=tribe.id,
                        description=truncate_string(tribe.description, 100)
                        if tribe.description
                        else None,
                    )
                    for tribe in tribes
                ],
            ),
            SelectMenu(
                placeholder="Choose an auspice",
                custom_id="auspice_id",
                options=[random_option]
                + [
                    discord.SelectOption(
                        label=auspice.name,
                        value=auspice.id,
                        description=truncate_string(auspice.description, 100)
                        if auspice.description
                        else None,
                    )
                    for auspice in auspices
                ],
            ),
        ]
        tribe_auspice_view = SelectMenuView(
            select_menus=tribe_auspice_menus, author=self.ctx.author
        )
        await self.interaction.edit(content="Choose a tribe and auspice!", view=tribe_auspice_view)
        await tribe_auspice_view.wait()
        if tribe_auspice_view.cancelled:
            await self._cancel_character_generation()

        self.werewolf_tribe_id = (
            None
            if tribe_auspice_view.selections["tribe_id"] == "NONE"
            else tribe_auspice_view.selections["tribe_id"]
        )
        self.werewolf_auspice_id = (
            None
            if tribe_auspice_view.selections["auspice_id"] == "NONE"
            else tribe_auspice_view.selections["auspice_id"]
        )

    async def _display_character_sheet(self) -> None:
        """Display the character sheet."""
        embed = await first_page_of_character_sheet_as_embed(
            ctx=self.ctx,
            character=self.character,
            title=f"{EmojiDict.YES} Created {self.character.name_full}\n",
            description_suffix="\n\nConfirm to create the character or cancel to start over.",
        )
        view = ConfirmCancelButtons(author=self.ctx.author)

        await self.interaction.edit(content=None, embed=embed, view=view)

        await view.wait()
        if view.cancelled:
            await self._cancel_character_generation(delete_character=True)

        if view.confirmed:
            return

    async def _update_channels(self) -> None:
        """Update the channels."""
        db_character = await DBCharacter.get_or_none(api_id=self.character.id)
        if not db_character:
            logger.error(f"Character not found in database: {self.character.id}")
            return

        channel_manager = ChannelManager(guild=self.ctx.guild)
        await channel_manager.confirm_character_channel(
            character=db_character, campaign=self.db_campaign
        )
        await channel_manager.sort_campaign_channels(self.db_campaign)
