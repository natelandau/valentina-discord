"""Dice roll workflow components for displaying and interacting with roll results."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
import inflect
from discord.ui import Button

from vbot.constants import EmbedColor, EmojiDict

if TYPE_CHECKING:
    from vclient.models import CharacterTrait, Diceroll

    from vbot.bot import ValentinaContext


p = inflect.engine()

__all__ = ("ReRollButton", "RollDisplay")


class ReRollButton(discord.ui.View):
    """Add a re-roll button to a view.  When desperation botch is True, choices to enter Overreach or Despair will replace the re-roll button."""

    def __init__(
        self,
        *,
        author: discord.User | discord.Member | None = None,
        diceroll: Diceroll,
    ):
        super().__init__(timeout=60)

        self.author = author
        self.diceroll = diceroll
        self.reroll: bool = None
        self.overreach: bool = False
        self.despair: bool = False

        if (
            self.diceroll.num_desperation_dice == 0
        ):  # Add reroll and done buttons if not a desperation roll
            reroll_button: Button = Button(
                label="Re-Roll",
                custom_id="reroll",
                style=discord.ButtonStyle.success,
            )
            reroll_button.callback = self.button_callback  # type: ignore [method-assign]
            self.add_item(reroll_button)

            done_button: Button = Button(
                label="Done",
                custom_id="done",
                style=discord.ButtonStyle.secondary,
            )
            done_button.callback = self.button_callback  # type: ignore [method-assign]
            self.add_item(done_button)
        elif self.diceroll.result.desperation_roll.count(1) > 0:
            overreach_button: Button = Button(
                label=f"{EmojiDict.OVERREACH} Succeed and increase danger!",
                custom_id="overreach",
                style=discord.ButtonStyle.success,
            )
            overreach_button.callback = self.button_callback  # type: ignore [method-assign]
            self.add_item(overreach_button)

            despair_button: Button = Button(
                label=f"{EmojiDict.DESPAIR} Fail and enter Despair!",
                custom_id="despair",
                style=discord.ButtonStyle.success,
            )
            despair_button.callback = self.button_callback  # type: ignore [method-assign]
            self.add_item(despair_button)

    async def button_callback(self, interaction: discord.Interaction) -> None:
        """Respond to the button press and update the view."""
        # Get the custom_id of the button that was pressed
        response = interaction.data.get("custom_id", None)

        # Disable the interaction and grab the setting name
        for child in self.children:
            if isinstance(child, Button) and response == child.custom_id:
                child.label = f"{EmojiDict.YES} {child.label}"

        self._disable_all()
        await interaction.response.edit_message(view=None)  # view=None remove all buttons

        if response == "done":
            self.reroll = False
        if response == "reroll":
            self.reroll = True
        if response == "overreach":
            self.reroll = False
            self.overreach = True
        if response == "despair":
            self.reroll = False
            self.despair = True

        self.stop()

    def _disable_all(self) -> None:
        """Disable all buttons in the view."""
        for child in self.children:
            if isinstance(child, Button | discord.ui.Select):
                child.disabled = True  # type: ignore [misc]

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Disables buttons for everyone except the user who created the embed."""
        if self.author is None:
            return True

        if self.author.guild_permissions.administrator:  # type: ignore [union-attr]
            return True

        return interaction.user.id == self.author.id


class RollDisplay:
    """Display and manipulate roll outcomes.

    This class is responsible for creating an embed message representing a roll.
    """

    def __init__(
        self,
        ctx: ValentinaContext,
        diceroll: Diceroll,
        trait_dtos_for_embed: list[CharacterTrait] = [],
    ):
        self.ctx = ctx
        self.diceroll = diceroll
        self.trait_dtos_for_embed = trait_dtos_for_embed

    def _add_comment_field(self, embed: discord.Embed) -> discord.Embed:
        """Add the comment field to the embed."""
        if self.diceroll.comment:
            embed.add_field(
                name="\u200b", value=f"**Comment**\n {self.diceroll.comment}", inline=False
            )

        return embed

    def _get_embed_color(self) -> int:
        """Get the embed color based on the roll result."""
        """Determine the Discord embed color based on the result of the roll.

        Return an integer color value corresponding to the roll result type.
        Use predefined color mappings for different roll outcomes:
        - OTHER: Info color
        - BOTCH: Error color
        - CRITICAL: Success color
        - SUCCESS: Success color
        - FAILURE: Warning color

        Returns:
            int: The color value to be used in the Discord embed.
        """
        color_map = {
            "OTHER": EmbedColor.INFO,
            "BOTCH": EmbedColor.ERROR,
            "CRITICAL": EmbedColor.SUCCESS,
            "SUCCESS": EmbedColor.SUCCESS,
            "FAILURE": EmbedColor.WARNING,
        }
        return color_map[self.diceroll.result.total_result_type].value

    async def get_embed(self) -> discord.Embed:
        """The graphical representation of the roll."""
        player_roll_string = self.diceroll.result.player_roll_emoji

        if self.diceroll.num_desperation_dice > 0:
            desperation_roll_string = self.diceroll.result.desperation_roll_emoji

        description = f"### {self.ctx.author.mention} rolled `{self.diceroll.num_desperation_dice + self.diceroll.num_dice}d{self.diceroll.dice_size}`"
        if self.diceroll.result.total_result_humanized:
            description += f"\n## {self.diceroll.result.total_result_humanized.upper()}"

        embed = discord.Embed(
            title=None,
            description=description,
            color=self._get_embed_color(),
        )

        # Rolled dice
        total_roll_string = f"{player_roll_string}"
        if self.diceroll.num_desperation_dice > 0:
            if player_roll_string:
                total_roll_string += " + "

            total_roll_string += f"{desperation_roll_string}"

        embed.add_field(name="Rolled Dice", value=f"{total_roll_string}", inline=False)

        num_desperation_botches = self.diceroll.result.desperation_roll.count(1)
        if self.diceroll.num_desperation_dice > 0 and num_desperation_botches > 0:
            embed.add_field(name="\u200b", value="\u200b", inline=False)  # spacer
            value = f"""\
> You must pick either:
> - {EmojiDict.DESPAIR} **Despair** (Fail your roll)
> - {EmojiDict.OVERREACH} **Overreach** (Succeed but raise the danger level by 1)
"""
            embed.add_field(
                name=f"**{EmojiDict.FACEPALM} {num_desperation_botches} Desperation {p.plural_noun('botch', num_desperation_botches)}**",
                value=f"{value}",
                inline=False,
            )

        if self.diceroll.difficulty:
            embed.add_field(name="Difficulty", value=f"`{self.diceroll.difficulty}`", inline=True)
            embed.add_field(
                name="Dice Pool",
                value=f"`{self.diceroll.num_dice}d{self.diceroll.dice_size}`",
                inline=True,
            )

        if self.diceroll.num_desperation_dice > 0:
            embed.add_field(
                name="Desperation Pool",
                value=f"`{self.diceroll.num_desperation_dice}d{self.diceroll.dice_size}`",
                inline=True,
            )

        if self.trait_dtos_for_embed:
            embed.add_field(name="\u200b", value="**TRAITS**", inline=False)
            for trait_dto in self.trait_dtos_for_embed:
                embed.add_field(
                    name=f"{trait_dto.trait.name}",
                    value=f"`{trait_dto.value} {p.plural_noun('die', trait_dto.value)}`",
                    inline=True,
                )

        return self._add_comment_field(embed)

    async def display(self) -> None:
        """Display the roll."""
        embed = await self.get_embed()
        await self.ctx.respond(embed=embed)
