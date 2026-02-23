"""Modals for the bot."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import discord
from discord.ui import InputText, Modal

from vbot.constants import EmbedColor
from vbot.views import ConfirmCancelButtons

if TYPE_CHECKING:
    from vclient.models import (
        Campaign,
        CampaignBook,
        CampaignChapter,
        Character,
        InventoryItem,
        Note,
        User,
    )


__all__ = (
    "CampaignModal",
    "CharacterInventoryItemModal",
    "CharacterNameBioModal",
    "NoteModal",
    "UserModal",
)


class NoteModal(Modal):
    """Modal for editing an inventory item."""

    def __init__(
        self,
        existing_object: Note | None = None,
        *args: InputText,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.note_title: str = ""
        self.content: str = ""
        self.existing_object: Note | None = existing_object

        self.add_item(
            InputText(
                label="note_title",
                placeholder="Enter a title",
                value=existing_object.title if existing_object else None,
                required=True,
                style=discord.InputTextStyle.short,
            ),
        )
        self.add_item(
            InputText(
                label="content",
                placeholder="Enter the content of the note (markdown is supported)",
                value=existing_object.content if existing_object else None,
                required=True,
                style=discord.InputTextStyle.long,
                max_length=1200,
            ),
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """Callback for the modal."""
        view = ConfirmCancelButtons(interaction.user)
        self.note_title = self.children[0].value
        self.content = self.children[1].value

        embed = discord.Embed(title="Confirmation", color=EmbedColor.INFO.value)
        embed.add_field(name="Title", value=self.note_title)
        embed.add_field(name="Content", value=self.content)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        await view.wait()
        if view.confirmed:
            self.confirmed = True
            await interaction.delete_original_response()
        else:
            self.confirmed = False
            await interaction.edit_original_response(
                embeds=[discord.Embed(title="Cancelled", color=EmbedColor.ERROR.value)],
            )

        self.stop()


class CharacterNameBioModal(Modal):
    """Modal for editing a character."""

    def __init__(
        self,
        existing_object: Character | None = None,
        *args: InputText,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.name_first: str = ""
        self.name_last: str = ""
        self.name_nick: str = ""
        self.biography: str = ""
        self.confirmed: bool = False
        self.cancelled: bool = False
        self.existing_object: Character | None = existing_object

        self.add_item(
            InputText(
                label="name_first",
                placeholder="First Name",
                value=existing_object.name_first if existing_object else None,
                required=True,
                style=discord.InputTextStyle.short,
            ),
        )
        self.add_item(
            InputText(
                label="name_last",
                placeholder="Last Name",
                value=existing_object.name_last if existing_object else None,
                required=True,
                style=discord.InputTextStyle.short,
            ),
        )
        nick_input = InputText(
            label="name_nick",
            placeholder="Nickname",
            value=existing_object.name_nick if existing_object else None,
            style=discord.InputTextStyle.short,
        )
        nick_input.required = False
        self.add_item(nick_input)

        bio_input = InputText(
            label="biography",
            placeholder="Enter a biography.",
            value=existing_object.biography if existing_object else None,
            style=discord.InputTextStyle.long,
            max_length=1200,
        )
        bio_input.required = False
        self.add_item(bio_input)

    async def callback(self, interaction: discord.Interaction) -> None:
        """Callback for the modal."""
        view = ConfirmCancelButtons(interaction.user)
        self.name_first = self.children[0].value
        self.name_last = self.children[1].value
        self.name_nick = self.children[2].value
        self.biography = self.children[3].value

        embed = discord.Embed(title="Confirmation", color=EmbedColor.INFO.value)
        embed.add_field(name="First Name", value=self.name_first)
        embed.add_field(name="Last Name", value=self.name_last)
        embed.add_field(name="Nickname", value=self.name_nick)
        embed.add_field(name="Biography", value=self.biography)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        await view.wait()
        if view.confirmed:
            self.confirmed = True
            await interaction.delete_original_response()
        else:
            self.cancelled = True
            await interaction.edit_original_response(
                embeds=[discord.Embed(title="Cancelled", color=EmbedColor.ERROR.value)],
            )

        self.stop()


class CharacterInventoryItemModal(Modal):
    """Modal for editing an inventory item."""

    def __init__(
        self,
        existing_object: InventoryItem | None = None,
        *args: InputText,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.name: str = ""
        self.description: str = ""
        self.existing_object: InventoryItem | None = existing_object

        self.add_item(
            InputText(
                label="name",
                placeholder="Enter a name",
                value=existing_object.name if existing_object else None,
                required=True,
                style=discord.InputTextStyle.short,
            ),
        )
        self.add_item(
            InputText(
                label="description",
                placeholder="Enter a description",
                value=existing_object.description if existing_object else None,
                required=False,
                style=discord.InputTextStyle.long,
                max_length=1200,
            ),
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """Callback for the modal."""
        view = ConfirmCancelButtons(interaction.user)
        self.name = self.children[0].value
        self.description = self.children[1].value

        embed = discord.Embed(title="Confirmation", color=EmbedColor.INFO.value)
        embed.add_field(name="Name", value=self.name)
        embed.add_field(name="Description", value=self.description)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        await view.wait()
        if view.confirmed:
            self.confirmed = True
            await interaction.delete_original_response()
        else:
            self.confirmed = False
            await interaction.edit_original_response(
                embeds=[discord.Embed(title="Cancelled", color=EmbedColor.ERROR.value)],
            )

        self.stop()


class UserModal(Modal):
    """Modal for creating or updating a user in the Valentina API."""

    def __init__(self, user: User | None = None, *args: InputText, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.name: str = ""
        self.email: str = ""
        self.confirmed: bool = False

        self.add_item(
            InputText(
                label="name",
                placeholder="Enter a name for the user",
                value=user.name if user else None,
                required=True,
                style=discord.InputTextStyle.short,
            ),
        )
        self.add_item(
            InputText(
                label="Contact Email",
                placeholder="Enter a contact email for the user",
                value=user.email if user else None,
                required=True,
                style=discord.InputTextStyle.short,
            ),
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """Callback for the modal."""
        view = ConfirmCancelButtons(interaction.user)
        self.name = self.children[0].value
        self.email = self.children[1].value

        embed = discord.Embed(title="Confirm User", color=EmbedColor.INFO.value)
        embed.add_field(name="Name", value=self.name)
        embed.add_field(name="Email", value=self.email)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        await view.wait()
        if view.confirmed:
            self.confirmed = True
            await interaction.delete_original_response()
        else:
            self.confirmed = False
            await interaction.edit_original_response(
                embeds=[discord.Embed(title="Cancelled", color=EmbedColor.ERROR.value)],
            )

        self.stop()


class CampaignModal(Modal):
    """Modal for creating a new campaign."""

    def __init__(
        self,
        exiting_object: Campaign | CampaignBook | CampaignChapter | None = None,
        *args: InputText,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.name: str = ""
        self.description: str = ""
        self.confirmed: bool = False
        self.exiting_object: Campaign | CampaignBook | CampaignChapter | None = exiting_object

        self.add_item(
            InputText(
                label="name",
                placeholder="Enter a name",
                value=exiting_object.name if exiting_object else None,
                required=True,
                style=discord.InputTextStyle.short,
            ),
        )
        self.add_item(
            InputText(
                label="description",
                placeholder="Enter a description.",
                value=exiting_object.description if exiting_object else None,
                required=False,
                style=discord.InputTextStyle.long,
                max_length=1200,
            ),
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """Callback for the modal."""
        view = ConfirmCancelButtons(interaction.user)
        self.name = self.children[0].value
        self.description = self.children[1].value

        embed = discord.Embed(
            title="Confirmation",
            color=EmbedColor.INFO.value,
            description=f"Are you sure you want to {'update' if self.exiting_object else 'create'} `{self.name}` with the following details?\n\n**Name:** {self.name}\n**Description:**\n{self.description}",
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        await view.wait()

        if view.confirmed:
            self.confirmed = True
            await interaction.delete_original_response()
        else:
            self.confirmed = False
            await interaction.edit_original_response(
                embeds=[discord.Embed(title="Cancelled", color=EmbedColor.ERROR.value)],
            )

        self.stop()
