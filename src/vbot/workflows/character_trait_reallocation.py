"""A wizard that walks the user through the character creation process."""

from dataclasses import dataclass

import discord
from discord.ui import Button
from vclient import (
    character_blueprint_service,
    character_traits_service,
    characters_service,
)
from vclient.exceptions import ValidationError
from vclient.models import Character, CharacterTrait, SheetSection, TraitCategory

from vbot.bot import ValentinaContext
from vbot.constants import MAX_BUTTONS_PER_ROW, EmbedColor, EmojiDict
from vbot.utils.strings import convert_int_to_emoji

__all__ = ("TraitValueReallocationHandler",)


class SelectTraitCategoryButtons(discord.ui.View):  # pragma: no cover
    """Buttons to select a trait category."""

    def __init__(
        self,
        ctx: ValentinaContext,
        character_dto: Character,
        category_dtos: list[TraitCategory],
    ):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.character_dto = character_dto
        self.category_dtos = category_dtos
        self.cancelled: bool = False
        self.selected_category: TraitCategory = None

        # Create a button for each category
        for i, category in enumerate(self.category_dtos):
            button: Button = Button(
                label=f"{i + 1}. {category.name.title()}",
                custom_id=f"{i}",
                style=discord.ButtonStyle.primary,
                row=i // 3,
            )
            button.callback = self.button_callback  # type: ignore [method-assign]
            self.add_item(button)

        rows = len(self.category_dtos) // 3
        cancel_button: Button = Button(
            label=f"{EmojiDict.CANCEL} Cancel",
            style=discord.ButtonStyle.secondary,
            custom_id="cancel",
            row=rows + 1 if rows < 4 else 4,  # noqa: PLR2004
        )
        cancel_button.callback = self.cancel_callback  # type: ignore [method-assign]
        self.add_item(cancel_button)

    def _disable_all(self) -> None:
        """Disable all buttons in the view."""
        for child in self.children:
            if isinstance(child, Button | discord.ui.Select):
                child.disabled = True  # type: ignore [misc]

    async def button_callback(self, interaction: discord.Interaction) -> None:
        """Respond to selecting a category."""
        await interaction.response.defer()
        # Disable the interaction and grab the setting name
        self._disable_all()

        # Return the selected character based on the custom_id of the button that was pressed
        index = int(interaction.data.get("custom_id", None))  # type: ignore[call-overload]
        self.selected_category = self.category_dtos[index]

        self.stop()

    async def cancel_callback(self, interaction: discord.Interaction) -> None:
        """Disable all buttons and stop the view."""
        await interaction.response.defer()
        self._disable_all()
        self.cancelled = True
        self.stop()


class SelectCharacterTraitButtons(discord.ui.View):  # pragma: no cover
    """Buttons to select a specific trait."""

    def __init__(
        self,
        *,
        ctx: ValentinaContext,
        trait_dtos: list[CharacterTrait],
        not_maxed_only: bool = False,
    ):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.not_maxed_only = not_maxed_only
        self.cancelled: bool = False
        self.selected_trait: CharacterTrait = None
        self.trait_dtos = trait_dtos

        # Create a button for each trait
        for i, trait in enumerate(self.trait_dtos):
            # Add the button
            button: Button = Button(
                label=f"{i + 1}. {trait.trait.name.title()}",
                custom_id=f"{i}",
                style=discord.ButtonStyle.primary,
            )
            button.callback = self.button_callback  # type: ignore [method-assign]
            self.add_item(button)

        cancel_button: Button = Button(
            label=f"{EmojiDict.CANCEL} Cancel",
            style=discord.ButtonStyle.secondary,
            custom_id="cancel",
        )
        cancel_button.callback = self.cancel_callback  # type: ignore [method-assign]
        self.add_item(cancel_button)

    def _disable_all(self) -> None:
        """Disable all buttons in the view."""
        for child in self.children:
            if isinstance(child, Button | discord.ui.Select):
                child.disabled = True  # type: ignore [misc]

    async def button_callback(self, interaction: discord.Interaction) -> None:
        """Respond to selecting a trait."""
        await interaction.response.defer()
        self._disable_all()

        # Return the selected character based on the custom_id of the button that was pressed
        index = int(interaction.data.get("custom_id", None))  # type: ignore[call-overload]
        self.selected_trait = self.trait_dtos[index]
        self.stop()

    async def cancel_callback(self, interaction: discord.Interaction) -> None:
        """Disable all buttons and stop the view."""
        await interaction.response.defer()
        self._disable_all()
        self.cancelled = True
        self.stop()


@dataclass
class DotSelection:
    """A selection of dots to reallocate."""

    new_value: int
    starting_points: int


class DotSelectionButtons(discord.ui.View):
    """Buttons to select the number of dots to reallocate."""

    def __init__(
        self,
        dot_selections: list[DotSelection],
        author: discord.User | discord.Member | None = None,
    ):
        super().__init__()
        self.author = author
        self.dot_selections = dot_selections
        self.selected_dot_selection: DotSelection = None
        self.selection: int = None
        self.cancelled = False

        for i, dot_selection in enumerate(dot_selections):
            button: Button = Button(
                label=f"{convert_int_to_emoji(num=dot_selection.new_value)} ({dot_selection.starting_points} points)",
                custom_id=str(i),
                style=discord.ButtonStyle.primary,
            )
            button.callback = self.button_callback  # type: ignore [method-assign]
            self.add_item(button)

        rows = len(dot_selections) // MAX_BUTTONS_PER_ROW

        cancel_button: Button = Button(
            label=f"{EmojiDict.CANCEL} Cancel",
            style=discord.ButtonStyle.secondary,
            custom_id="cancel",
            row=rows + 1 if rows < 4 else 4,  # noqa: PLR2004
        )
        cancel_button.callback = self.cancel_callback  # type: ignore [method-assign]
        self.add_item(cancel_button)

    def _disable_all(self) -> None:
        """Disable all buttons in the view."""
        for child in self.children:
            if isinstance(child, Button | discord.ui.Select):
                child.disabled = True  # type: ignore [misc]

    async def button_callback(self, interaction: discord.Interaction) -> None:
        """Respond to selecting a dot selection."""
        await interaction.response.defer()
        self._disable_all()

        # Return the new value selected by the user
        index = int(interaction.data.get("custom_id", None))  # type: ignore[call-overload]
        self.selection = self.dot_selections[index].new_value
        self.stop()

    async def cancel_callback(self, interaction: discord.Interaction) -> None:
        """Disable all buttons and stop the view."""
        await interaction.response.defer()
        self._disable_all()
        self.cancelled = True
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Disables buttons for everyone except the user who created the embed."""
        if self.author is None:
            return True

        if self.author.guild_permissions.administrator:  # type: ignore [union-attr]
            return True

        return interaction.user.id == self.author.id


class TraitValueReallocationHandler:  # pragma: no cover
    """Guide the user through the process of reallocating trait dots for a character.

    The wizard interacts with the user using Discord embeds and buttons. The process involves:
    - Choosing the trait category.
    - Selecting the source trait (from where dots will be taken).
    - Selecting the target trait (to where dots will be added).
    - Specifying the number of dots to reallocate.
    - Executing the reallocation and updating the character's trait values.
    """

    def __init__(
        self,
        ctx: ValentinaContext,
        character_dto: Character,
        user_api_id: str,
    ):
        self.ctx = ctx
        self.character_dto = character_dto
        self.user_api_id = user_api_id

        # Character and traits attributes
        self.category_dto: TraitCategory = None

        # Available sections, categories, and traits
        self.available_sheet_sections: list[SheetSection] = None
        self.available_categories: list[TraitCategory] = None

        # Wizard state
        self.msg: discord.WebhookMessage = None
        self.cancelled: bool = False

    async def _get_available_sections_categories(self) -> None:
        """Get the available sections, categories, and traits."""
        available_sheet_sections = await character_blueprint_service().list_all_sections(
            game_version=self.character_dto.game_version,
            character_class=self.character_dto.character_class,
        )

        available_categories = []
        for section in available_sheet_sections:
            categories = await character_blueprint_service().list_all_categories(
                game_version=self.character_dto.game_version,
                section_id=section.id,
                character_class=self.character_dto.character_class,
            )
            available_categories.extend(categories)

        attributes_section_id = next(
            (section.id for section in available_sheet_sections if section.name == "Attributes"),
            None,
        )
        abilities_section_id = next(
            (section.id for section in available_sheet_sections if section.name == "Abilities"),
            None,
        )
        for category in available_categories:
            if (
                category.parent_sheet_section_id == attributes_section_id
                and not category.name.startswith("Attributes: ")
            ):
                category.name = "Attributes: " + category.name
            elif (
                category.parent_sheet_section_id == abilities_section_id
                and not category.name.startswith("Abilities: ")
            ):
                category.name = "Abilities: " + category.name

        self.available_sheet_sections = available_sheet_sections
        self.available_categories = [
            category
            for category in available_categories
            if category.name not in ["Gifts", "Renown", "Virtues", "Spheres", "Resonance"]
        ]

    async def refund_wizard(self) -> tuple[bool, Character]:
        """Launch the dot refund wizard to guide the user through the process.

        Returns:
            tuple (bool, Character): A boolean indicating if the character was updated, and the updated character object.
        """
        await self._get_available_sections_categories()

        # Prompt user for trait category
        if not self.cancelled:
            self.category_dto = await self._prompt_for_category()

        # Prompt user for trait to take from
        if not self.cancelled:
            character_trait = await self._prompt_for_character_trait_to_reduce()

        if not self.cancelled:
            new_value = await self._prompt_for_dots_to_reduce(character_trait)

        if not self.cancelled:
            self.character_dto = await self._update_trait_value(
                character_trait=character_trait, new_value=new_value
            )

        # Return the result based on the state of self.cancelled
        return (not self.cancelled, self.character_dto)

    async def purchase_wizard(self) -> tuple[bool, Character]:
        """Launch the dot purchase wizard to guide the user through the process.

        Returns:
            tuple (bool, Character): A boolean indicating if the character was updated, and the updated character object.
        """
        await self._get_available_sections_categories()

        # Prompt user for trait category
        if not self.cancelled:
            self.category_dto = await self._prompt_for_category()

        # Prompt user for trait to add dots to
        if not self.cancelled:
            character_trait = await self._prompt_for_character_trait_to_purchase()

        if not self.cancelled:
            new_value = await self._prompt_for_dots_to_purchase(character_trait)

        if not self.cancelled:
            self.character_dto = await self._update_trait_value(
                character_trait=character_trait, new_value=new_value
            )

        # Return the result based on the state of self.cancelled
        return (not self.cancelled, self.character_dto)

    async def _cancel_wizard(self, msg: str | None = None) -> None:
        """Cancel the wizard."""
        if not msg:
            msg = "Cancelled"

        embed = discord.Embed(
            title="Reallocate dots",
            description=f"{EmojiDict.CANCEL} {msg}",
            color=EmbedColor.WARNING.value,
        )
        await self.msg.edit(embed=embed, view=None)
        await self.msg.delete(delay=5.0)
        self.cancelled = True

    async def _prompt_for_category(self) -> TraitCategory:
        """Terminate the reallocation wizard and inform the user.

        This method updates the Discord embed with a cancellation message, deletes the embed after a short delay, and sets the internal state as cancelled.

        Returns:
            TraitCategory: The trait category the user chose.
            None if the wizard is cancelled.
        """
        # Set up the view and embed to prompt the user to select a trait category
        view = SelectTraitCategoryButtons(
            ctx=self.ctx, character_dto=self.character_dto, category_dtos=self.available_categories
        )
        embed = discord.Embed(
            title="Reallocate Dots",
            description="Select the **category** of the traits you want to reallocate",
            color=EmbedColor.INFO.value,
        )

        # Show the embed to the user and wait for their response
        self.msg = await self.ctx.respond(embed=embed, view=view, ephemeral=True)  # type: ignore [assignment]
        await view.wait()

        # Handle user cancellation
        if view.cancelled:
            await self._cancel_wizard()
            return None

        return view.selected_category

    async def _prompt_for_character_trait_to_reduce(self) -> CharacterTrait:
        """Prompt the user to choose a trait from which dots will be taken."""
        # All traits in the category
        available_trait_dtos = await character_traits_service(
            user_id=self.user_api_id,
            campaign_id=self.character_dto.campaign_id,
            character_id=self.character_dto.id,
        ).list_all(
            parent_category_id=self.category_dto.id,
        )

        # Set up the view and embed to prompt the user to select a trait which has dots to take from
        view = SelectCharacterTraitButtons(
            ctx=self.ctx,
            trait_dtos=[x for x in available_trait_dtos if x.value > x.trait.min_value],
        )
        embed = discord.Embed(
            title="Reallocate Dots",
            description=f"Select the {self.category_dto.name} **trait** you want to _take dots from_",
            color=EmbedColor.INFO.value,
        )

        # Show the embed to the user and wait for their response
        await self.msg.edit(embed=embed, view=view)
        await view.wait()

        # Handle user cancellation
        if view.cancelled:
            await self._cancel_wizard()
            return None

        return view.selected_trait

    async def _prompt_for_character_trait_to_purchase(self) -> CharacterTrait:
        """Prompt the user to choose a trait from which dots will be added."""
        # Determine the traits that can be used as a target
        available_trait_dtos = await character_traits_service(
            user_id=self.user_api_id,
            campaign_id=self.character_dto.campaign_id,
            character_id=self.character_dto.id,
        ).list_all(
            parent_category_id=self.category_dto.id,
        )

        # Set up the view and embed to prompt the user to select a trait
        view = SelectCharacterTraitButtons(
            ctx=self.ctx,
            trait_dtos=[x for x in available_trait_dtos if x.value < x.trait.max_value],
        )

        embed = discord.Embed(
            title="Reallocate Dots",
            description=f"Select the {self.category_dto.name} **trait** you want to _purchase dots for_",
            color=EmbedColor.INFO.value,
        )

        # Show the embed to the user and wait for their response
        await self.msg.edit(embed=embed, view=view)
        await view.wait()

        # Handle user cancellation
        if view.cancelled:
            await self._cancel_wizard()
            return None

        # Store the user's trait selection and its current value and max value
        return view.selected_trait

    async def _prompt_for_dots_to_reduce(self, character_trait_to_reduce: CharacterTrait) -> int:
        """Prompt the user to select the new value for the character trait.

        Args:
            character_trait_to_reduce: The character trait to reduce the value of.

        Returns:
            int: The new value for the character trait.
        """
        trait_value_options = await character_traits_service(
            user_id=self.user_api_id,
            campaign_id=self.character_dto.campaign_id,
            character_id=self.character_dto.id,
        ).get_value_options(
            character_trait_id=character_trait_to_reduce.id,
        )
        dot_selections = []
        for value, info in trait_value_options.options.items():
            if info.direction == "decrease":
                dot_selections.append(
                    DotSelection(new_value=int(value), starting_points=info.point_change)
                )

        # If no dots are available, cancel the wizard and inform the user
        if not dot_selections:
            await self._cancel_wizard(
                f"Cannot refund dots from {character_trait_to_reduce.trait.name} because no dots are available",
            )
            return None

        # If only one dot is available, return it
        if len(dot_selections) == 1:
            return dot_selections[0].new_value

        # Otherwise, prompt the user to select the number of dots to refund
        view = DotSelectionButtons(dot_selections=dot_selections, author=self.ctx.author)
        embed = discord.Embed(
            title="Reallocate Dots",
            description=f"Select the reduced value for `{character_trait_to_reduce.trait.name}`",
            color=EmbedColor.INFO.value,
        )
        await self.msg.edit(embed=embed, view=view)
        await view.wait()

        # Handle user cancellation
        if view.cancelled:
            await self._cancel_wizard()
            return None

        return view.selection

    async def _prompt_for_dots_to_purchase(
        self, character_trait_to_purchase: CharacterTrait
    ) -> int:
        """Prompt the user to select the number of dots to purchase for the character trait."""
        trait_value_options = await character_traits_service(
            user_id=self.user_api_id,
            campaign_id=self.character_dto.campaign_id,
            character_id=self.character_dto.id,
        ).get_value_options(
            character_trait_id=character_trait_to_purchase.id,
        )
        dot_selections = []
        for value, info in trait_value_options.options.items():
            if info.direction == "increase":
                dot_selections.append(
                    DotSelection(new_value=int(value), starting_points=info.point_change)
                )

        # If no dots are available, cancel the wizard and inform the user
        if not dot_selections:
            await self._cancel_wizard(
                f"Cannot purchase dots for {character_trait_to_purchase.trait.name} because no dots are available",
            )
            return None

        # If only one dot is available, return it
        if len(dot_selections) == 1:
            return dot_selections[0].new_value

        # Otherwise, prompt the user to select the number of dots to purchase
        view = DotSelectionButtons(dot_selections=dot_selections, author=self.ctx.author)
        embed = discord.Embed(
            title="Reallocate Dots",
            description=f"Select the new value you wish to purchase for `{character_trait_to_purchase.trait.name}`",
            color=EmbedColor.INFO.value,
        )
        await self.msg.edit(embed=embed, view=view)
        await view.wait()

        # Handle user cancellation
        if view.cancelled:
            await self._cancel_wizard()
            return None

        return view.selection

    async def _update_trait_value(
        self, character_trait: CharacterTrait, new_value: int
    ) -> Character:
        """Update the value of a character trait."""
        try:
            await character_traits_service(
                user_id=self.user_api_id,
                campaign_id=self.character_dto.campaign_id,
                character_id=self.character_dto.id,
            ).change_value(
                character_trait_id=character_trait.id,
                new_value=new_value,
                currency="STARTING_POINTS",
            )
        except ValidationError as e:
            await self._cancel_wizard(
                f"Failed to update trait value: {e.detail}",
            )
            return None
        else:
            # Update the embed to inform the user of the success
            embed = discord.Embed(
                title="Reallocate Dots",
                description=f"{EmojiDict.SUCCESS} Updated `{character_trait.trait.name}` to `{new_value}`",
                color=EmbedColor.SUCCESS.value,
            )
            await self.msg.edit(embed=embed, view=None)

            # Delete the embed after a short delay
            await self.msg.delete(delay=5.0)

        return await characters_service(
            user_id=self.user_api_id,
            campaign_id=self.character_dto.campaign_id,
        ).get(
            character_id=self.character_dto.id,
        )
