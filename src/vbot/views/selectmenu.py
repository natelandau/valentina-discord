"""Select menu views."""

from dataclasses import dataclass

import discord
from discord.ui import Button

from vbot.constants import EmojiDict

__all__ = ("SelectMenu", "SelectMenuView")


@dataclass
class SelectMenu:
    """Option for a select menu."""

    placeholder: str
    custom_id: str
    options: list[discord.SelectOption]
    min_values: int = 1
    max_values: int = 1


class SelectMenuView(discord.ui.View):
    """View for selecting one or more dropdown menus."""

    def __init__(
        self,
        *,
        select_menus: list[SelectMenu],
        author: discord.User | discord.Member | None = None,
    ) -> None:
        super().__init__()
        self.select_menus = select_menus
        self.cancelled = False
        self.selections: dict[str, str] = {}
        self.author = author

        for select_menu in select_menus:
            select: discord.ui.Select = discord.ui.Select(
                placeholder=select_menu.placeholder,
                custom_id=select_menu.custom_id,
                min_values=select_menu.min_values,
                max_values=select_menu.max_values,
                options=sorted(select_menu.options, key=lambda x: x.label),
            )
            select.callback = self.select_callback  # type: ignore [method-assign]
            self.add_item(select)

        submit_button: Button = Button(
            label=f"{EmojiDict.YES} Submit",
            style=discord.ButtonStyle.primary,
            custom_id="submit",
            row=len(select_menus) + 1 if len(select_menus) <= 3 else 4,  # noqa: PLR2004
        )
        submit_button.callback = self.submit_callback  # type: ignore [method-assign]
        self.add_item(submit_button)

        cancel_button: Button = Button(
            label=f"{EmojiDict.CANCEL} Cancel",
            style=discord.ButtonStyle.secondary,
            custom_id="cancel",
            row=len(select_menus) + 1 if len(select_menus) <= 3 else 4,  # noqa: PLR2004
        )
        cancel_button.callback = self.cancel_callback  # type: ignore [method-assign]
        self.add_item(cancel_button)

    async def select_callback(self, interaction: discord.Interaction) -> None:
        """Callback for the select menu."""
        await interaction.response.defer()
        custom_id = interaction.data.get("custom_id", None)

        for child in self.children:
            if isinstance(child, discord.ui.Select) and child.custom_id == custom_id:
                self.selections[child.custom_id] = child.values[0]
                break

        await self.wait()

    async def submit_callback(self, interaction: discord.Interaction) -> None:
        """Callback for the submit button."""
        for child in self.children:
            if isinstance(child, discord.ui.Select) and (not child.values or not child.values[0]):
                await interaction.response.send_message(
                    content="You must select a value for all select menus.",
                    ephemeral=True,
                    delete_after=3,
                )

                await self.wait()
                return
        self.disable_all_items()
        await interaction.response.edit_message(view=self)

        self.stop()

    async def cancel_callback(self, interaction: discord.Interaction) -> None:
        """Callback for the cancel button."""
        self.disable_all_items()
        await interaction.response.edit_message(view=self)
        self.cancelled = True
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Disables buttons for everyone except the user who created the embed."""
        if self.author is None:
            return True

        if self.author.guild_permissions.administrator:  # type: ignore [union-attr]
            return True

        return interaction.user.id == self.author.id
