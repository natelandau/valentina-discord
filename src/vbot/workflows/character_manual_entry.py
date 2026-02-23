"""Manual entry wizard for creating a character."""

from dataclasses import dataclass
from textwrap import dedent

import discord
from discord.ui import Button
from loguru import logger
from vclient import character_blueprint_service, characters_service, options_service
from vclient.constants import CharacterClass, CharacterType, GameVersion
from vclient.models import (
    Character,
    CharacterCreate,
    CharacterCreateTraitAssign,
    HunterAttributesCreate,
    MageAttributes,
    Trait,
    VampireAttributesCreate,
    WerewolfAttributesCreate,
)

from vbot.bot import ValentinaContext
from vbot.constants import MAX_BUTTONS_PER_ROW, EmojiDict
from vbot.db.models import DBCampaign, DBCharacter
from vbot.handlers import character_handler
from vbot.lib.channel_mngr import ChannelManager
from vbot.lib.exceptions import CancellationActionError
from vbot.utils.strings import truncate_string
from vbot.views import CharacterNameBioModal, ConfirmCancelButtons, SelectMenu, SelectMenuView

from .character_sheet import first_page_of_character_sheet_as_embed

__all__ = ("CharacterManualEntryHandler",)


class TraitValueButtons(discord.ui.View):
    """Buttons to select a trait value."""

    def __init__(
        self,
        trait: Trait,
    ):
        super().__init__(timeout=300)
        self.trait = trait
        self.trait_value = None
        self.possible_values = list(range(self.trait.min_value, self.trait.max_value + 1))
        self.cancelled = False

        for i, possible_value in enumerate(self.possible_values):
            button: Button = Button(
                label=str(possible_value),
                custom_id=str(i),
                style=discord.ButtonStyle.primary
                if possible_value > self.trait.min_value
                else discord.ButtonStyle.success,
            )
            button.callback = self.button_callback  # type: ignore [method-assign]
            self.add_item(button)

        rows = len(self.possible_values) // MAX_BUTTONS_PER_ROW

        cancel_button: Button = Button(
            label=f"{EmojiDict.CANCEL} Cancel Character Creation",
            style=discord.ButtonStyle.secondary,
            custom_id="cancel",
            row=rows + 1 if rows < 4 else 4,  # noqa: PLR2004
        )
        cancel_button.callback = self.cancel_callback  # type: ignore [method-assign]
        self.add_item(cancel_button)

    async def button_callback(self, interaction: discord.Interaction) -> None:
        """Respond to selecting a dot selection."""
        await interaction.response.defer()
        self.disable_all_items()
        index = int(interaction.data.get("custom_id", None))  # type: ignore[call-overload]
        self.trait_value = self.possible_values[index]

        self.stop()

    async def cancel_callback(self, interaction: discord.Interaction) -> None:
        """Disable all buttons and stop the view."""
        await interaction.response.defer()
        self.disable_all_items()
        self.cancelled = True
        self.stop()


@dataclass
class CharacterCreateData:
    character_class: CharacterClass | None = None
    game_version: GameVersion | None = None

    name_first: str | None = None
    name_last: str | None = None
    name_nick: str | None = None
    biography: str | None = None

    concept_id: str | None = None

    vampire_attributes: VampireAttributesCreate | None = None
    werewolf_attributes: WerewolfAttributesCreate | None = None
    hunter_attributes: HunterAttributesCreate | None = None
    mage_attributes: MageAttributes | None = None


class CharacterManualEntryHandler:
    """Manual entry wizard for creating a character."""

    def __init__(
        self,
        ctx: ValentinaContext,
        db_campaign: DBCampaign,
        api_user_id: str,
        character_type: CharacterType = "PLAYER",
    ):
        self.ctx = ctx
        self.db_campaign = db_campaign
        self.api_user_id = api_user_id
        self.interaction: discord.Interaction | discord.WebhookMessage = None
        self.api_options: dict[str, dict[str, list[str] | dict[str, str]]] | None = None
        self.cancelled = False
        self.character_type: CharacterType = character_type

        ## TRAIT VALUE SELECTION #########
        self.all_traits: list[Trait] = []
        self.advantage_traits: list[Trait] = []
        self.all_traits_except_advantages: list[Trait] = []
        self.completed_traits: list[CharacterCreateTraitAssign] = []

        ## INITIALIZE CHARACTER DATA #########
        self.create_data = CharacterCreateData()

        self.character: Character | None = None

    async def start(self) -> None:
        """Guide the user through the manual entry wizard."""
        self.api_options = await options_service().get_options()

        await self._get_name_and_bio()
        await self._select_version_class()
        await self._select_concept()

        if self.create_data.character_class in ["VAMPIRE", "GHOUL"]:
            await self._select_clan()
        if self.create_data.character_class == "WEREWOLF":
            await self._select_tribe_auspice()
        # TODO: Support Mage and Hunter characters

        ## TRAIT VALUE SELECTION #########
        await self._build_trait_lists()
        previous_trait = None
        previous_trait_value = None
        for trait in self.all_traits_except_advantages:
            value = await self._get_trait_value(
                trait=trait,
                previous_trait=previous_trait,
                previous_trait_value=previous_trait_value,
            )
            previous_trait = trait
            previous_trait_value = value

        # TODO: Add advantages to the character

        request = CharacterCreate(
            name_first=self.create_data.name_first,
            name_last=self.create_data.name_last,
            name_nick=self.create_data.name_nick,
            biography=self.create_data.biography,
            character_class=self.create_data.character_class,
            game_version=self.create_data.game_version,
            type=self.character_type,
            concept_id=self.create_data.concept_id,
            vampire_attributes=self.create_data.vampire_attributes,
            werewolf_attributes=self.create_data.werewolf_attributes,
            hunter_attributes=self.create_data.hunter_attributes,
            mage_attributes=self.create_data.mage_attributes,
            traits=self.completed_traits,
        )

        self.character = await characters_service(
            user_id=self.api_user_id,
            campaign_id=self.db_campaign.api_id,
        ).create(request=request)

        await self._display_character_sheet()
        await character_handler.update_or_create_character_in_db(self.character)
        await self._update_channels()

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

        msg = "Character creation cancelled. No character was created."
        raise CancellationActionError(msg)

    async def _get_name_and_bio(self) -> None:
        """Get the name and bio from the user."""
        modal = CharacterNameBioModal(title="Name your character")
        self.interaction = await self.ctx.send_modal(modal)
        await modal.wait()
        if modal.cancelled:
            await self._cancel_character_generation()

        self.create_data.name_first = modal.name_first
        self.create_data.name_last = modal.name_last
        self.create_data.name_nick = modal.name_nick
        self.create_data.biography = modal.biography

    async def _select_version_class(self) -> None:
        """Get the game version and character class from the user."""
        game_versions = self.api_options["characters"]["GameVersion"]
        character_classes = self.api_options["characters"]["CharacterClass"]

        version_class_menus = [
            SelectMenu(
                placeholder="Choose a game version",
                custom_id="game_version",
                options=[
                    discord.SelectOption(
                        label=game_version,
                        value=game_version,
                        description="Traits will be customized for this game version.",
                    )
                    for game_version in game_versions
                ],
            ),
            SelectMenu(
                placeholder="Choose a character class",
                custom_id="character_class",
                options=[
                    discord.SelectOption(
                        label=character_class.title(),
                        value=character_class,
                        emoji=getattr(EmojiDict, character_class.upper()),
                    )
                    for character_class in character_classes
                ],
            ),
        ]
        version_class_view = SelectMenuView(
            select_menus=version_class_menus, author=self.ctx.author
        )

        self.interaction = await self.ctx.respond(
            "Choose a game version and character class!",
            view=version_class_view,
            ephemeral=True,
        )
        await version_class_view.wait()
        if version_class_view.cancelled:
            await self._cancel_character_generation()

        self.create_data.game_version = version_class_view.selections["game_version"]  # type: ignore [assignment]
        self.create_data.character_class = version_class_view.selections["character_class"]  # type: ignore [assignment]

    async def _select_clan(self) -> None:
        """Get the clan from the user."""
        clans = await character_blueprint_service().list_all_vampire_clans(
            game_version=self.create_data.game_version
        )

        clan_menus = [
            SelectMenu(
                placeholder="Choose a clan",
                custom_id="clan_id",
                options=[
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

        self.create_data.vampire_attributes = VampireAttributesCreate(
            clan_id=clan_view.selections["clan_id"]
        )

    async def _select_tribe_auspice(self) -> None:
        """Get the tribe and auspice from the user."""
        tribes = await character_blueprint_service().list_all_werewolf_tribes(
            game_version=self.create_data.game_version
        )
        auspices = await character_blueprint_service().list_all_werewolf_auspices(
            game_version=self.create_data.game_version
        )
        tribe_auspice_menus = [
            SelectMenu(
                placeholder="Choose a tribe",
                custom_id="tribe_id",
                options=[
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
                options=[
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

        self.create_data.werewolf_attributes = WerewolfAttributesCreate(
            tribe_id=tribe_auspice_view.selections["tribe_id"],
            auspice_id=tribe_auspice_view.selections["auspice_id"],
        )

    async def _select_concept(self) -> None:
        """Get the concept from the user."""
        concepts = await character_blueprint_service().list_all_concepts()
        concept_menus = [
            SelectMenu(
                placeholder="Choose a concept",
                custom_id="concept_id",
                options=[
                    discord.SelectOption(
                        label=concept.name,
                        value=concept.id,
                        description=truncate_string(concept.description, 100),
                        emoji=getattr(
                            EmojiDict, concept.name.upper().replace("-", "_"), EmojiDict.OTHER
                        ),
                    )
                    for concept in concepts
                ],
            ),
        ]
        concept_view = SelectMenuView(select_menus=concept_menus, author=self.ctx.author)
        await self.interaction.edit(content="Choose a concept!", view=concept_view)
        await concept_view.wait()
        if concept_view.cancelled:
            await self._cancel_character_generation()

        self.create_data.concept_id = concept_view.selections["concept_id"]

    async def _build_trait_lists(self) -> None:
        """Build the trait list."""
        self.all_traits = await character_blueprint_service().list_all_traits(
            game_version=self.create_data.game_version,
            character_class=self.create_data.character_class,
            order_by="SHEET",
        )

        self.advantage_traits = [x for x in self.all_traits if x.sheet_section_name == "Advantages"]
        self.all_traits_except_advantages = [
            x for x in self.all_traits if x.sheet_section_name != "Advantages"
        ]

    async def _get_trait_value(
        self,
        trait: Trait,
        previous_trait: Trait | None = None,
        previous_trait_value: int | None = None,
    ) -> int:
        """Get the trait value from the user."""
        view = TraitValueButtons(trait=trait)

        if not previous_trait:
            message = dedent(f"""
            ```text
            Cycle through all your traits, and choose a value for each one. The Character will not be saved until this is completed.
            ```
            ### Choose a value for {trait.name}
            """).strip()
        else:
            message = dedent(f"""
            __Successfully set {previous_trait.name} to {previous_trait_value}.__
            ### Choose a value for {trait.name}
            """).strip()

        await self.interaction.edit(content=message, view=view)

        await view.wait()
        if view.cancelled:
            await self._cancel_character_generation()

        self.completed_traits.append(
            CharacterCreateTraitAssign(
                trait_id=trait.id,
                value=view.trait_value,
            ),
        )

        return view.trait_value

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
