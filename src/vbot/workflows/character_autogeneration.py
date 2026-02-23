"""Wizard for the character generation process."""

from textwrap import dedent

import discord
import inflect
from discord.ext import pages
from discord.ui import Button
from loguru import logger
from vclient import (
    character_autogen_service,
    character_blueprint_service,
    characters_service,
    options_service,
)
from vclient.models import Character, ChargenSessionResponse, Company

from vbot.bot import ValentinaContext
from vbot.constants import EmbedColor, EmojiDict
from vbot.db.models import DBCharacter
from vbot.handlers import character_handler
from vbot.lib.channel_mngr import ChannelManager
from vbot.views import CharacterNameBioModal

from .character_sheet import first_page_of_character_sheet_as_embed
from .character_trait_reallocation import TraitValueReallocationHandler

__all__ = ("CharacterAutogenerationHandler",)

p = inflect.engine()


class BeginCancelCharGenButtons(discord.ui.View):  # pragma: no cover
    """Manage buttons for initiating or canceling the character generation process.

    This view provides buttons for users to either start rolling characters or cancel the process.

    Args:
        author (discord.User | discord.Member | None): The author of the interaction.
            If provided, only this user can interact with the buttons.

    Attributes:
        roll (bool | None): Indicates whether to roll for characters.
            Set to True if the roll button is clicked, False if cancelled, None otherwise.
    """

    def __init__(self, author: discord.User | discord.Member | None = None):
        super().__init__()
        self.author = author
        self.roll: bool = None

    def _disable_all(self) -> None:
        """Disable all buttons in the view."""
        for child in self.children:
            if isinstance(child, Button | discord.ui.Select):
                child.disabled = True  # type: ignore [misc]

    @discord.ui.button(
        label=f"{EmojiDict.DICE} Roll Characters (10xp)",
        style=discord.ButtonStyle.success,
        custom_id="roll",
        row=2,
    )
    async def roll_callback(self, button: Button, interaction: discord.Interaction) -> None:
        """Callback for the roll button."""
        await interaction.response.defer()
        button.label += f" {EmojiDict.YES}"
        self._disable_all()

        self.roll = True
        self.stop()

    @discord.ui.button(
        label=f"{EmojiDict.CANCEL} Cancel",
        style=discord.ButtonStyle.secondary,
        custom_id="cancel",
        row=2,
    )
    async def cancel_callback(self, button: Button, interaction: discord.Interaction) -> None:
        """Callback for the cancel button."""
        button.label += f" {EmojiDict.YES}"
        button.disabled = True
        self._disable_all()
        await interaction.response.edit_message(view=None)  # view=None remove all buttons
        self.roll = False
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Disables buttons for everyone except the user who created the embed."""
        if self.author is None:
            return True
        return interaction.user.id == self.author.id


class CharacterPickerButtons(discord.ui.View):  # pragma: no cover
    """Manage buttons for selecting a character in the CharGenWizard paginator.

    Args:
        ctx (ValentinaContext): The context of the Discord application.
        characters (list[Character]): List of characters to choose from.

    Attributes:
        pick_character (bool): Whether a character was picked.
        selected (Character): The selected character.
        reroll (bool): Whether to reroll characters.
        cancelled (bool): Whether the selection was cancelled.
    """

    def __init__(self, ctx: ValentinaContext, characters: list[Character]):
        super().__init__(timeout=3000)
        self.ctx = ctx
        self.characters = characters
        self.pick_character: bool = False
        self.selected: Character | None = None
        self.reroll: bool = False
        self.cancelled: bool = False

        # Create a button for each character
        for i, character in enumerate(characters):
            button: Button = Button(
                label=f"{i + 1}. {character.name}",
                custom_id=f"{i}",
                style=discord.ButtonStyle.primary,
            )
            button.callback = self.button_callback  # type: ignore [method-assign]
            self.add_item(button)

    async def button_callback(self, interaction: discord.Interaction) -> None:
        """Respond to selecting a character."""
        await interaction.response.defer()
        self._disable_all()
        index = int(interaction.data.get("custom_id", None))  # type: ignore[call-overload]
        self.selected = self.characters[index]
        self.pick_character = True
        self.stop()

    def _disable_all(self) -> None:
        """Disable all buttons in the view."""
        for child in self.children:
            if isinstance(child, Button | discord.ui.Select):
                child.disabled = True  # type: ignore [misc]

    @discord.ui.button(
        label=f"{EmojiDict.DICE} Reroll (XP will be lost)",
        style=discord.ButtonStyle.secondary,
        custom_id="reroll",
        row=2,
    )
    async def reroll_callback(
        self,
        button: Button,  # noqa: ARG002
        interaction: discord.Interaction,
    ) -> None:
        """Disable all buttons and stop the view."""
        await interaction.response.defer()
        self._disable_all()
        self.reroll = True
        self.stop()

    @discord.ui.button(
        label=f"{EmojiDict.CANCEL} Cancel (XP will be lost)",
        style=discord.ButtonStyle.secondary,
        custom_id="cancel",
        row=2,
    )
    async def cancel_callback(
        self,
        button: Button,  # noqa: ARG002
        interaction: discord.Interaction,
    ) -> None:
        """Disable all buttons and stop the view."""
        await interaction.response.defer()
        self._disable_all()
        self.cancelled = True
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Disables buttons for everyone except the user who created the embed."""
        return interaction.user.id == self.ctx.author.id


class UpdateCharacterButtons(discord.ui.View):  # pragma: no cover
    """Manage buttons for updating a character's attributes.

    This view provides interactive buttons for various character update operations, such as renaming the character or reallocating attribute dots.

    Args:
        ctx (ValentinaContext): The context of the Discord application.
        character (Character): The character to update.
        author (discord.User | discord.Member | None): The author of the interaction.

    Attributes:
        updated (bool): Indicates whether the character has been updated.
        done (bool): Indicates whether the update process is complete.
    """

    def __init__(
        self,
        ctx: ValentinaContext,
        character_dto: Character,
        user_api_id: str,
        author: discord.User | discord.Member | None = None,
    ):
        super().__init__()
        self.ctx = ctx
        self.character_dto = character_dto
        self.author = author
        self.user_api_id = user_api_id
        self.updated: bool = False
        self.done: bool = False

    def _disable_all(self) -> None:
        """Disable all buttons in the view."""
        for child in self.children:
            if isinstance(child, Button | discord.ui.Select):
                child.disabled = True  # type: ignore [misc]

    @discord.ui.button(
        label=f"{EmojiDict.PENCIL} Rename",
        style=discord.ButtonStyle.primary,
        custom_id="rename",
        row=2,
    )
    async def rename_callback(
        self,
        button: Button,  # noqa: ARG002
        interaction: discord.Interaction,
    ) -> None:
        """Callback for the rename button."""
        self._disable_all()

        modal = CharacterNameBioModal(existing_object=self.character_dto, title="Rename Character")
        await interaction.response.send_modal(modal)
        await modal.wait()
        if not modal.confirmed:
            self.updated = True
            self.stop()
        else:
            self.character_dto = await characters_service(
                user_id=self.user_api_id,
                campaign_id=self.character_dto.campaign_id,
            ).update(
                character_id=self.character_dto.id,
                name_first=modal.name_first,
                name_last=modal.name_last,
                name_nick=modal.name_nick,
                biography=modal.biography,
            )

            self.updated = True
            self.stop()

    @discord.ui.button(
        label=f"{EmojiDict.REFUND} Reduce dots to add starting points",
        style=discord.ButtonStyle.primary,
        custom_id="refund",
        row=2,
    )
    async def refund_callback(self, button: Button, interaction: discord.Interaction) -> None:  # noqa: ARG002
        """Callback for the refund button."""
        await interaction.response.defer()
        self._disable_all()

        dot_wizard = TraitValueReallocationHandler(
            ctx=self.ctx,
            character_dto=self.character_dto,
            user_api_id=self.user_api_id,
        )
        updated, character_dto = await dot_wizard.refund_wizard()
        if updated:
            self.character_dto = character_dto

        self.updated = True
        self.stop()

    @discord.ui.button(
        label=f"{EmojiDict.PURCHASE} Spend starting points to add dots",
        style=discord.ButtonStyle.primary,
        custom_id="purchase",
        row=2,
    )
    async def purchase_callback(
        self,
        button: Button,  # noqa: ARG002
        interaction: discord.Interaction,
    ) -> None:
        """Callback for the purchase button."""
        await interaction.response.defer()
        self._disable_all()

        dot_wizard = TraitValueReallocationHandler(
            ctx=self.ctx, character_dto=self.character_dto, user_api_id=self.user_api_id
        )
        updated, character_dto = await dot_wizard.purchase_wizard()
        if updated:
            self.character_dto = character_dto

        self.updated = True
        self.stop()

    @discord.ui.button(
        label=f"{EmojiDict.YES} Done",
        style=discord.ButtonStyle.success,
        custom_id="done",
        row=3,
    )
    async def done_callback(self, button: Button, interaction: discord.Interaction) -> None:
        """Callback for the done button."""
        await interaction.response.defer()
        button.disabled = True
        self._disable_all()
        self.done = True
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Disables buttons for everyone except the user who created the embed."""
        return interaction.user.id == self.ctx.author.id


class CharacterAutogenerationHandler:  # pragma: no cover
    """Guide the user through a step-by-step character generation process.

    This class manages the interactive process of creating a new character,
    handling user inputs and generating character attributes.
    """

    def __init__(
        self,
        ctx: ValentinaContext,
        company_dto: Company,
        user_api_id: str,
        campaign_api_id: str,
    ) -> None:
        self.ctx = ctx
        self.company_dto = company_dto
        self.user_api_id = user_api_id
        self.campaign_api_id = campaign_api_id
        self.xp_cost = company_dto.settings.character_autogen_xp_cost
        self.num_choices = company_dto.settings.character_autogen_num_choices
        self.chargen_session_dto: ChargenSessionResponse | None = None
        self.paginator: pages.Paginator = None  # Initialize paginator to None

    async def _cancel_character_generation(
        self,
        msg: str | None = None,
    ) -> None:
        """Cancel the character generation process and clean up resources.

        This method handles the cancellation of character generation, deleting any partially
        created characters and displaying a cancellation message to the user.

        Args:
            msg (str | None): Custom message to display upon cancellation. If None, a default message is used.
        """
        if not msg:
            msg = "No character was created."

        cancel_embed = discord.Embed(
            title=f"{EmojiDict.CANCEL} Cancelled",
            description=msg,
            color=EmbedColor.WARNING.value,
        )
        cancel_embed.set_thumbnail(url=self.ctx.bot.user.display_avatar)
        await self.paginator.cancel(page=cancel_embed, include_custom=False)

    async def start(self, *, restart: bool = False) -> None:
        """Initiate the character generation wizard.

        Start or restart the character generation process, presenting the user with
        instructional embeds and options to begin or cancel character creation.

        Args:
            restart (bool): If True, restart the wizard with existing paginator.
                If False, create a new paginator. Defaults to False.
        """
        logger.debug("Starting the character generation wizard.")

        character_concepts = await character_blueprint_service().list_all_concepts()
        api_options = await options_service().get_options()
        character_class_percentile_chance = api_options["character_autogeneration"][
            "CharacterClassPercentileChance"
        ]

        # Build the instructional embeds
        embed1 = discord.Embed(
            title="Create a new character",
            description=dedent(f"""\
                For the cost of {self.xp_cost}xp, I will generate {self.num_choices} {p.plural_noun("character", self.num_choices)} for you to choose between.
                ### How this works
                By rolling percentile dice we select a class and a concept.  The concept guides the background, specialties, and traits of your character.

                Once you select a character you can re-allocate dots and change the name, but you cannot change the concept, class, or clan.

                *View the possible classes and concepts by scrolling through the pages below*
            """),
            color=EmbedColor.INFO.value,
        )
        embed2 = discord.Embed(
            title="Classes",
            description="\n".join(
                [f"- **{x}**" for x in character_class_percentile_chance],
            ),
            color=EmbedColor.INFO.value,
        )
        embed3 = discord.Embed(
            title="Concepts",
            description="\n".join(
                [f"- **{c.name}** {c.description}" for c in character_concepts],
            ),
            color=EmbedColor.INFO.value,
        )
        # Create and display the paginator
        view = BeginCancelCharGenButtons(self.ctx.author)
        if restart:
            await self.paginator.update(pages=[embed1, embed2, embed3], custom_view=view)  # type: ignore [arg-type]
        else:
            self.paginator = pages.Paginator(
                pages=[embed1, embed2, embed3],  # type: ignore [arg-type]
                custom_view=view,
                author_check=True,
                timeout=600,
            )
            self.paginator.remove_button("first")
            self.paginator.remove_button("last")
            await self.paginator.respond(self.ctx.interaction, ephemeral=False)

        await view.wait()

        if not view.roll:
            await self._cancel_character_generation()
            return

        self.chargen_session_dto = await character_autogen_service(
            user_id=self.user_api_id, campaign_id=self.campaign_api_id
        ).start_chargen_session()

        # Move on reviewing options
        await self.present_character_choices()

    async def present_character_choices(self) -> None:
        """Guide the user through the character selection process.

        Generate random characters and present them to the user for selection. Display character details using a paginator, allowing the user to review and choose a character, reroll for new options, or cancel the process.

        This method handles the core logic of character generation and selection, including trait assignment and presentation of character options.

        Returns:
            None
        """
        logger.debug("Starting the character selection process")
        characters = self.chargen_session_dto.characters
        # Add the pages to the paginator
        description = f"## Created {len(characters)} {p.plural_noun('character', len(characters))} for you to choose from\n"

        character_list = []
        for i, character in enumerate(characters, start=1):
            clan = character.vampire_attributes.clan_name if character.vampire_attributes else None
            tribe = (
                character.werewolf_attributes.tribe_name if character.werewolf_attributes else None
            )
            auspice = (
                character.werewolf_attributes.auspice_name
                if character.werewolf_attributes
                else None
            )
            werewolf_specifics = (
                f"{tribe} ({auspice})" if tribe and auspice else tribe or (auspice or "")
            )
            # TODO: Support hunters and mages
            class_specifics = clan or (werewolf_specifics or "")
            concept = (
                await character_blueprint_service().get_concept(concept_id=character.concept_id)
                if character.concept_id
                else None
            )
            character_list.append(
                f"{i}. **{character.name}:**  A {concept.name if concept else '-'} {character.character_class.title()} {class_specifics}"
            )

        description += "\n".join(character_list)
        description += dedent(f"""
            ### Next Steps
            1. **Review the details for each character** by scrolling through their sheets
            2. **Select the character you want to play** by selecting a button below; or
            3. **Reroll all characters** by selecting the reroll button for a cost of  {self.xp_cost}xp

            **Important:**
            Once you select a character you can re-allocate dots and change the name, but you cannot change the concept, class, or clan.
        """)

        pages: list[discord.Embed] = [
            discord.Embed(
                title="Character Generations",
                description=description,
                color=EmbedColor.INFO.value,
            ),
        ]
        pages.extend(
            [
                await first_page_of_character_sheet_as_embed(self.ctx, character=character)
                for character in characters
            ],
        )

        # present the character selection paginator
        view = CharacterPickerButtons(self.ctx, characters)
        await self.paginator.update(
            pages=pages,  # type: ignore [arg-type]
            custom_view=view,
            timeout=600,
        )
        await view.wait()

        if view.cancelled:
            await self._cancel_character_generation(
                msg=f"No character was created but you lost {self.xp_cost} XP for wasting my time.",
            )
            return

        if view.reroll:
            await self.start(restart=True)

        if view.pick_character:
            selected_character = await character_autogen_service(
                user_id=self.user_api_id,
                campaign_id=self.campaign_api_id,
            ).finalize_chargen_session(
                session_id=self.chargen_session_dto.session_id,
                selected_character_id=view.selected.id,
            )

            # Post-process the selected character
            await character_handler.update_or_create_character_in_db(selected_character)
            await self.finalize_character_selection(selected_character)

    async def finalize_character_selection(self, character_dto: Character) -> None:
        """Review and finalize the selected character.

        Present the user with an updated character sheet and allow them to finalize
        the character or make additional changes.

        Args:
            character_dto (Character): The selected character to review and finalize.
        """
        logger.debug(f"CHARGENL Update the character: {character_dto.name_full}")

        # Create the character sheet embed
        embed = await first_page_of_character_sheet_as_embed(
            self.ctx,
            character=character_dto,
            title=f"{EmojiDict.YES} Created {character_dto.name_full}\n",
            description_suffix=dedent(f"""
                **Next Steps:**
                - Rename the character by clicking the "Rename" button below
                - Reduce a trait's value to add to the starting points pool by clicking the "Reduce trait value to add starting points" button below
                - Add dots to a trait to reduce the starting points pool by clicking the "Add dots to a trait to reduce the starting points pool" button below
                - Done by clicking the "Done" button below

                **Important:**  Once you select "Done" you will not be able to spend available starting points.

                **Available starting points:** `{character_dto.starting_points}`
            """),
        )

        # Update the paginator
        view = UpdateCharacterButtons(
            self.ctx,
            character_dto=character_dto,
            author=self.ctx.author,
            user_api_id=self.user_api_id,
        )
        await self.paginator.update(
            pages=[embed],  # type: ignore [arg-type]
            custom_view=view,
            show_disabled=False,
            show_indicator=False,
            timeout=600,
        )

        await view.wait()
        if view.updated:
            # Restart the view and show the changes
            await self.finalize_character_selection(view.character_dto)
        if view.done:
            await self.paginator.update(pages=[embed], custom_view=None)  # type: ignore [arg-type]

        db_character = await DBCharacter.get_or_none(api_id=character_dto.id)
        if not db_character:
            logger.error(f"Character not found in database: {character_dto.id}")
            return

        await db_character.fetch_related("campaign")
        channel_manager = ChannelManager(guild=self.ctx.guild)
        await channel_manager.confirm_character_channel(
            character=db_character, campaign=db_character.campaign
        )
        await channel_manager.sort_campaign_channels(db_character.campaign)
