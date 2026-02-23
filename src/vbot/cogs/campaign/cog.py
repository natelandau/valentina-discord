"""Campaign cog."""

import contextlib
from typing import Annotated

import discord
from discord.commands import Option
from discord.ext import commands
from vclient import chapters_service

from vbot.bot import Valentina, ValentinaContext
from vbot.cogs import autocompletion
from vbot.cogs.campaign.lib import build_campaign_list_text
from vbot.constants import EmbedColor
from vbot.db.models import DBCampaign
from vbot.handlers import book_handler, campaign_handler
from vbot.lib import exceptions
from vbot.utils.discord import fetch_channel_object
from vbot.utils.strings import truncate_string
from vbot.views import CampaignModal, auto_paginate, present_embed
from vbot.workflows import CampaignViewer, confirm_action


class CampaignCog(commands.Cog):
    """Campaign cog."""

    def __init__(self, bot: Valentina):
        self.bot = bot

    campaign = discord.SlashCommandGroup(
        name="campaign",
        description="Manage your campaigns",
    )
    book = campaign.create_subgroup(name="book", description="Manage campaign books")
    chapter = campaign.create_subgroup(name="chapter", description="Manage campaign chapters")

    @campaign.command(name="list", description="List all campaigns")
    async def campaign_list(
        self,
        ctx: ValentinaContext,
        hidden: Annotated[
            bool,
            Option(
                name="hidden",
                description="Make the response visible only to you (default true).",
                required=False,
                default=True,
            ),
        ],
    ) -> None:
        """List all campaigns."""
        text = await build_campaign_list_text(
            user_api_id=await ctx.get_api_user_id(),
            guild_name=ctx.guild.name,
        )

        if text is None:
            await present_embed(
                ctx,
                title="No campaigns",
                description="There are no campaigns\nCreate one with `/campaign create`",
                level="info",
                ephemeral=hidden,
            )
            return

        await auto_paginate(
            ctx=ctx,
            title="",
            text=text,
            color=EmbedColor.INFO,
            hidden=hidden,
            max_chars=900,
        )

    @campaign.command(name="create", description="Create a new campaign")
    async def campaign_create(
        self,
        ctx: ValentinaContext,
        hidden: Annotated[
            bool,
            Option(
                name="hidden",
                description="Make the response visible only to you (default true).",
                required=False,
                default=True,
            ),
        ],
    ) -> None:
        """Create a new campaign."""
        modal = CampaignModal(title=truncate_string("Create new Campaign", 45))
        await ctx.send_modal(modal)
        await modal.wait()
        if not modal.confirmed:
            return

        campaign_name = modal.name
        campaign_description = modal.description

        await campaign_handler.create_campaign(
            ctx=ctx,
            name=campaign_name,
            description=campaign_description,
        )

        await present_embed(
            ctx,
            title=f"Create Campaign: `{campaign_name}`",
            level="success",
            description="Campaign created successfully.",
            ephemeral=hidden,
            inline_fields=True,
        )

    @campaign.command(name="edit", description="Edit a campaign")
    async def campaign_edit(
        self,
        ctx: ValentinaContext,
        campaign_api_id: Annotated[
            str,
            Option(
                autocomplete=autocompletion.select_campaign,
                name="campaign",
                description="The campaign to edit.",
                required=True,
            ),
        ],
        hidden: Annotated[
            bool,
            Option(
                name="hidden",
                description="Make the response visible only to you (default true).",
                required=False,
                default=True,
            ),
        ],
    ) -> None:
        """Edit a campaign."""
        api_user_id = await ctx.get_api_user_id()

        campaign = await campaign_handler.get_campaign(
            user_api_id=api_user_id, campaign_api_id=campaign_api_id
        )
        original_name = campaign.name

        modal = CampaignModal(title=truncate_string("Edit Campaign", 45), exiting_object=campaign)
        await ctx.send_modal(modal)
        await modal.wait()
        if not modal.confirmed:
            return

        new_name = modal.name if modal.name != original_name else None
        campaign_description = modal.description

        await campaign_handler.update_campaign(
            ctx=ctx,
            campaign_api_id=campaign_api_id,
            name=new_name,
            description=campaign_description,
        )

        await present_embed(
            ctx,
            title=f"Edit Campaign: `{campaign.name}`",
            level="success",
            description="Campaign updated successfully.",
            ephemeral=hidden,
            inline_fields=True,
        )

    @campaign.command(name="delete", description="Delete a campaign")
    async def campaign_delete(
        self,
        ctx: ValentinaContext,
        campaign_api_id: Annotated[
            str,
            Option(
                autocomplete=autocompletion.select_campaign,
                name="campaign_id",
                description="The ID of the campaign to delete.",
                required=True,
            ),
        ],
        hidden: Annotated[
            bool,
            Option(
                name="hidden",
                description="Make the response visible only to you (default true).",
                required=False,
                default=True,
            ),
        ],
    ) -> None:
        """Delete a campaign."""
        db_campaign = await DBCampaign.get_or_none(api_id=campaign_api_id)

        title = f"Delete Campaign: `{db_campaign.name}`" if db_campaign else "Delete Campaign"
        description = (
            "This is an irreversible action. Are you sure you want to delete this campaign?"
        )
        is_confirmed, msg, confirmation_embed = await confirm_action(
            ctx, title=title, description=description, hidden=hidden
        )
        if not is_confirmed:
            return

        await campaign_handler.delete_campaign(ctx=ctx, campaign_api_id=campaign_api_id)

        confirmation_embed.description = "Campaign deleted successfully."
        await msg.edit_original_response(embed=confirmation_embed, view=None)

    @campaign.command(name="view", description="View a campaign. (Will only be visible to you)")
    async def campaign_view(
        self,
        ctx: ValentinaContext,
        campaign_api_id: Annotated[
            str,
            Option(
                autocomplete=autocompletion.select_campaign,
                name="campaign",
                description="The campaign to view.",
                required=True,
            ),
        ],
    ) -> None:
        """View a campaign."""
        api_user_id = await ctx.get_api_user_id()
        campaign = await campaign_handler.get_campaign(
            user_api_id=api_user_id, campaign_api_id=campaign_api_id
        )

        viewer = CampaignViewer(
            ctx=ctx,
            api_user_id=api_user_id,
            campaign=campaign,
        )
        paginator = await viewer.display()
        await paginator.respond(ctx.interaction, ephemeral=True)
        await paginator.wait()

    @campaign.command(name="set_danger", description="Set the danger level for a campaign")
    async def campaign_set_danger(
        self,
        ctx: ValentinaContext,
        danger: Annotated[
            int, Option(int, "The danger level to set for the campaign", required=True)
        ],
    ) -> None:
        """Set the danger level for a campaign."""
        channel_objects = await fetch_channel_object(ctx, need_campaign=True)
        db_campaign = channel_objects.campaign

        if danger < 0 or danger > 5:  # noqa: PLR2004
            await present_embed(
                ctx,
                title="Invalid Danger Level",
                description="The danger level must be between 0 and 5.",
                level="error",
                ephemeral=True,
            )
            return

        title = f"Set Danger Level for Campaign: `{db_campaign.name}`"
        description = f"Are you sure you want to set the danger level for the campaign to {danger}?"
        is_confirmed, interaction, confirmation_embed = await confirm_action(
            ctx, title=title, description=description, hidden=True
        )
        if not is_confirmed:
            return

        await campaign_handler.update_campaign(
            ctx=ctx,
            campaign_api_id=db_campaign.api_id,
            danger=danger,
        )

        confirmation_embed.description = "Danger level set successfully."
        await interaction.edit_original_response(embed=confirmation_embed, view=None)

    @campaign.command(
        name="set_desperation", description="Set the desperation level for a campaign"
    )
    async def campaign_set_desperation(
        self,
        ctx: ValentinaContext,
        desperation: Annotated[
            int, Option(int, "The desperation level to set for the campaign", required=True)
        ],
    ) -> None:
        """Set the desperation level for a campaign."""
        channel_objects = await fetch_channel_object(ctx, need_campaign=True)
        db_campaign = channel_objects.campaign

        if desperation < 0 or desperation > 5:  # noqa: PLR2004
            await present_embed(
                ctx,
                title="Invalid Desperation Level",
                description="The desperation level must be between 0 and 5.",
                level="error",
                ephemeral=True,
            )
            return

        title = f"Set Desperation Level for Campaign: `{db_campaign.name}`"
        description = (
            f"Are you sure you want to set the desperation level for the campaign to {desperation}?"
        )
        is_confirmed, interaction, confirmation_embed = await confirm_action(
            ctx, title=title, description=description, hidden=True
        )
        if not is_confirmed:
            return

        await campaign_handler.update_campaign(
            ctx=ctx,
            campaign_api_id=db_campaign.api_id,
            desperation=desperation,
        )

        confirmation_embed.description = "Desperation level set successfully."
        await interaction.edit_original_response(embed=confirmation_embed, view=None)

    ### BOOK COMMANDS ####################################################################

    @book.command(name="create", description="Create a new book")
    async def campaign_book_create(
        self,
        ctx: ValentinaContext,
        hidden: Annotated[
            bool,
            Option(
                name="hidden",
                description="Make the response visible only to you (default true).",
                required=False,
                default=True,
            ),
        ],
    ) -> None:
        """Create a new book."""
        channel_objects = await fetch_channel_object(ctx, need_campaign=True)
        db_campaign = channel_objects.campaign

        modal = CampaignModal(title=truncate_string("Create new Book", 45))
        await ctx.send_modal(modal)
        await modal.wait()
        if not modal.confirmed:
            return

        book_name = modal.name
        book_description = modal.description

        book = await book_handler.create_book(
            ctx=ctx,
            campaign_api_id=db_campaign.api_id,
            book_name=book_name,
            book_description=book_description,
        )

        await present_embed(
            ctx,
            title=f"Create Book: `{book.name}`",
            level="success",
            description="Book created successfully.",
            ephemeral=hidden,
        )

    @book.command(name="edit", description="Edit a book")
    async def campaign_book_edit(
        self,
        ctx: ValentinaContext,
        hidden: Annotated[
            bool,
            Option(
                name="hidden",
                description="Make the response visible only to you (default true).",
                required=False,
                default=True,
            ),
        ],
    ) -> None:
        """Edit a book."""
        api_user_id = await ctx.get_api_user_id()
        channel_objects = await fetch_channel_object(
            ctx, need_campaign=True, need_book=True, refresh_from_api=True
        )
        db_campaign = channel_objects.campaign
        db_book = channel_objects.book
        book_dto = await book_handler.get_book(
            user_api_id=api_user_id,
            campaign_api_id=db_campaign.api_id,
            book_api_id=db_book.api_id,
        )

        modal = CampaignModal(title=truncate_string("Edit Book", 45), exiting_object=book_dto)
        await ctx.send_modal(modal)
        await modal.wait()
        if not modal.confirmed:
            return

        new_book_name = modal.name
        book_description = modal.description

        book = await book_handler.update_book(
            ctx=ctx,
            campaign_api_id=db_campaign.api_id,
            book_api_id=db_book.api_id,
            book_name=new_book_name if new_book_name != book_dto.name else None,
            book_description=book_description,
        )

        await present_embed(
            ctx,
            title=f"Edit Book: `{book.name}`",
            level="success",
            description="Book updated successfully.",
            ephemeral=hidden,
        )

    @book.command(name="delete", description="Delete a book")
    async def campaign_book_delete(
        self,
        ctx: ValentinaContext,
        hidden: Annotated[
            bool,
            Option(
                name="hidden",
                description="Make the response visible only to you (default true).",
                required=False,
                default=True,
            ),
        ],
    ) -> None:
        """Delete a book."""
        channel_objects = await fetch_channel_object(
            ctx, need_campaign=True, need_book=True, refresh_from_api=True
        )
        db_campaign = channel_objects.campaign
        db_book = channel_objects.book

        title = f"Delete book `{db_book.name}` from `{db_campaign.name}`"
        is_confirmed, interaction, confirmation_embed = await confirm_action(
            ctx, title=title, hidden=hidden
        )
        if not is_confirmed:
            return

        await book_handler.delete_book(
            ctx=ctx,
            campaign_api_id=db_campaign.api_id,
            book_api_id=db_book.api_id,
        )

        confirmation_embed.description = "Book deleted successfully."
        with contextlib.suppress(discord.errors.HTTPException):
            await interaction.edit_original_response(embed=confirmation_embed, view=None)

    @book.command(name="list", description="List all books")
    async def campaign_book_list(
        self,
        ctx: ValentinaContext,
        hidden: Annotated[
            bool,
            Option(
                name="hidden",
                description="Make the response visible only to you (default true).",
                required=False,
                default=True,
            ),
        ],
    ) -> None:
        """List all books."""
        api_user_id = await ctx.get_api_user_id()
        channel_objects = await fetch_channel_object(ctx, need_campaign=True, refresh_from_api=True)
        db_campaign = channel_objects.campaign
        books = await book_handler.list_books(
            user_api_id=api_user_id,
            campaign_api_id=db_campaign.api_id,
        )
        if len(books) == 0:
            await present_embed(
                ctx,
                title="No Books",
                description="There are no books\nCreate one with `/campaign book create`",
                level="info",
            )
            return

        text = ""
        for book in books:
            chapters = await chapters_service(
                user_id=api_user_id, campaign_id=db_campaign.api_id, book_id=book.id
            ).list_all()
            text += f"- **Book #{book.number}: {book.name}**\n"
            if chapters:
                text += f"  - {('  - ').join([f'Chapter {chapter.number}. {chapter.name}\n' for chapter in sorted(chapters, key=lambda x: x.number)])}"

        await auto_paginate(
            ctx=ctx,
            title="Books",
            text=text,
            color=EmbedColor.INFO,
            hidden=hidden,
            max_chars=900,
        )

    @book.command(name="renumber", description="Renumber books")
    async def campaign_book_renumber(
        self,
        ctx: ValentinaContext,
        number: Annotated[
            int,
            Option(
                name="number",
                description="The number to renumber the book to.",
                required=True,
            ),
        ],
        hidden: Annotated[
            bool,
            Option(
                name="hidden",
                description="Make the response visible only to you (default true).",
                required=False,
                default=True,
            ),
        ],
    ) -> None:
        """Renumber books."""
        channel_objects = await fetch_channel_object(
            ctx, need_campaign=True, need_book=True, refresh_from_api=True
        )
        db_campaign = channel_objects.campaign
        db_book = channel_objects.book

        if number <= 0 or number > len(await db_campaign.books.all()):
            msg = "The number must be greater than 0 and less than the number of books in the campaign."
            raise exceptions.ValidationError(msg)

        if number == db_book.number:
            msg = "The number is already the same as the current book number."
            raise exceptions.ValidationError(msg)

        title = f"Renumber Book: `{db_book.name}`"
        description = f"Are you sure you want to renumber the book to {number}?"
        is_confirmed, interaction, confirmation_embed = await confirm_action(
            ctx, title=title, description=description, hidden=hidden
        )
        if not is_confirmed:
            return

        await book_handler.renumber_book(
            ctx=ctx,
            campaign_api_id=db_campaign.api_id,
            book_api_id=db_book.api_id,
            number=number,
        )

        confirmation_embed.description = "Book renumbered successfully."
        with contextlib.suppress(discord.errors.HTTPException):
            await interaction.edit_original_response(embed=confirmation_embed, view=None)

    @book.command(name="view", description="View a book")
    async def campaign_book_view(
        self,
        ctx: ValentinaContext,
        hidden: Annotated[
            bool,
            Option(
                name="hidden",
                description="Make the response visible only to you (default true).",
                required=False,
                default=True,
            ),
        ],
    ) -> None:
        """View a book."""
        api_user_id = await ctx.get_api_user_id()
        channel_objects = await fetch_channel_object(
            ctx, need_campaign=True, need_book=True, refresh_from_api=True
        )
        db_campaign = channel_objects.campaign
        db_book = channel_objects.book
        book = await book_handler.get_book(
            user_api_id=api_user_id,
            campaign_api_id=db_campaign.api_id,
            book_api_id=db_book.api_id,
        )
        chapters = await chapters_service(
            user_id=api_user_id, campaign_id=db_campaign.api_id, book_id=db_book.api_id
        ).list_all()

        text = f"## Book #{db_book.number}: {db_book.name}\n"
        text += f"### Description\n{book.description}\n"
        if chapters:
            text += "### Chapters\n"
            text += f"- {('- ').join([f'Chapter {chapter.number}. {chapter.name}\n' for chapter in sorted(chapters, key=lambda x: x.number)])}"
        await auto_paginate(
            ctx=ctx,
            title="",
            text=text,
            color=EmbedColor.INFO,
            hidden=hidden,
            max_chars=900,
        )

    ### CHAPTER COMMANDS ####################################################################

    @chapter.command(name="create", description="Create a new chapter")
    async def campaign_chapter_create(
        self,
        ctx: ValentinaContext,
        hidden: Annotated[
            bool,
            Option(
                name="hidden",
                description="Make the response visible only to you (default true).",
                required=False,
                default=True,
            ),
        ],
    ) -> None:
        """Create a new chapter."""
        api_user_id = await ctx.get_api_user_id()
        channel_objects = await fetch_channel_object(
            ctx, need_campaign=True, need_book=True, refresh_from_api=True
        )
        db_campaign = channel_objects.campaign
        db_book = channel_objects.book

        modal = CampaignModal(title=truncate_string("Create new Chapter", 45))
        await ctx.send_modal(modal)
        await modal.wait()
        if not modal.confirmed:
            return

        chapter_name = modal.name
        chapter_description = modal.description

        await chapters_service(
            user_id=api_user_id, campaign_id=db_campaign.api_id, book_id=db_book.api_id
        ).create(name=chapter_name, description=chapter_description)

        await present_embed(
            ctx,
            title=f"Create Chapter: `{chapter_name}`",
            level="success",
            description="Chapter created successfully.",
            ephemeral=hidden,
        )

    @chapter.command(name="edit", description="Edit a chapter")
    async def campaign_chapter_edit(
        self,
        ctx: ValentinaContext,
        chapter_id: Annotated[
            str,
            Option(
                autocomplete=autocompletion.select_chapter,
                name="chapter_id",
                description="The ID of the chapter to edit.",
                required=True,
            ),
        ],
        hidden: Annotated[
            bool,
            Option(
                name="hidden",
                description="Make the response visible only to you (default true).",
                required=False,
                default=True,
            ),
        ],
    ) -> None:
        """Edit a chapter."""
        api_user_id = await ctx.get_api_user_id()
        channel_objects = await fetch_channel_object(
            ctx, need_campaign=True, need_book=True, refresh_from_api=True
        )
        db_campaign = channel_objects.campaign
        db_book = channel_objects.book

        chapter_dto = await chapters_service(
            user_id=api_user_id, campaign_id=db_campaign.api_id, book_id=db_book.api_id
        ).get(chapter_id)

        modal = CampaignModal(title=truncate_string("Edit Chapter", 45), exiting_object=chapter_dto)
        await ctx.send_modal(modal)
        await modal.wait()
        if not modal.confirmed:
            return

        chapter_name = modal.name
        chapter_description = modal.description

        await chapters_service(
            user_id=api_user_id, campaign_id=db_campaign.api_id, book_id=db_book.api_id
        ).update(chapter_id, name=chapter_name, description=chapter_description)

        await present_embed(
            ctx,
            title=f"Edit Chapter: `{chapter_name}`",
            level="success",
            description="Chapter updated successfully.",
            ephemeral=hidden,
        )

    @chapter.command(name="delete", description="Delete a chapter")
    async def campaign_chapter_delete(
        self,
        ctx: ValentinaContext,
        chapter_id: Annotated[
            str,
            Option(
                autocomplete=autocompletion.select_chapter,
                name="chapter_id",
                description="The ID of the chapter to delete.",
                required=True,
            ),
        ],
        hidden: Annotated[
            bool,
            Option(
                name="hidden",
                description="Make the response visible only to you (default true).",
                required=False,
                default=True,
            ),
        ],
    ) -> None:
        """Delete a chapter."""
        api_user_id = await ctx.get_api_user_id()
        channel_objects = await fetch_channel_object(
            ctx, need_campaign=True, need_book=True, refresh_from_api=True
        )
        db_campaign = channel_objects.campaign
        db_book = channel_objects.book

        chapter_dto = await chapters_service(
            user_id=api_user_id, campaign_id=db_campaign.api_id, book_id=db_book.api_id
        ).get(chapter_id)

        title = f"Delete Chapter: `{chapter_dto.name}`"
        description = (
            f"Are you sure you want to delete the chapter {chapter_dto.number}. {chapter_dto.name}?"
        )
        is_confirmed, interaction, confirmation_embed = await confirm_action(
            ctx, title=title, description=description, hidden=hidden
        )
        if not is_confirmed:
            return

        await chapters_service(
            user_id=api_user_id, campaign_id=db_campaign.api_id, book_id=db_book.api_id
        ).delete(chapter_id)

        confirmation_embed.description = "Chapter deleted successfully."
        await interaction.edit_original_response(embed=confirmation_embed, view=None)

    @chapter.command(name="list", description="List all chapters")
    async def campaign_chapter_list(
        self,
        ctx: ValentinaContext,
        hidden: Annotated[
            bool,
            Option(
                name="hidden",
                description="Make the response visible only to you (default true).",
                required=False,
                default=True,
            ),
        ],
    ) -> None:
        """List all chapters."""
        api_user_id = await ctx.get_api_user_id()
        channel_objects = await fetch_channel_object(
            ctx, need_campaign=True, need_book=True, refresh_from_api=True
        )
        db_campaign = channel_objects.campaign
        db_book = channel_objects.book

        chapters = await chapters_service(
            user_id=api_user_id, campaign_id=db_campaign.api_id, book_id=db_book.api_id
        ).list_all()
        if len(chapters) == 0:
            await present_embed(
                ctx,
                title="No Chapters",
                description="There are no chapters\nCreate one with `/campaign chapter create`",
                level="info",
                ephemeral=hidden,
            )
            return

        fields = []
        fields.extend(
            [
                (
                    f"**{chapter.number}.** **__{chapter.name}__**",
                    f"{truncate_string(chapter.description, 150)}",
                )
                for chapter in sorted(chapters, key=lambda x: x.number)
            ],
        )

        await present_embed(ctx, title="Chapters", fields=fields, level="info")

    @chapter.command(name="renumber", description="Renumber chapters")
    async def campaign_chapter_renumber(
        self,
        ctx: ValentinaContext,
        chapter_id: Annotated[
            str,
            Option(
                autocomplete=autocompletion.select_chapter,
                name="chapter_id",
                description="The ID of the chapter to renumber.",
                required=True,
            ),
        ],
        number: Annotated[
            int,
            Option(
                name="number", description="The number to renumber the chapter to.", required=True
            ),
        ],
        hidden: Annotated[
            bool,
            Option(
                name="hidden",
                description="Make the response visible only to you (default true).",
                required=False,
                default=True,
            ),
        ],
    ) -> None:
        """Renumber chapters."""
        api_user_id = await ctx.get_api_user_id()
        channel_objects = await fetch_channel_object(
            ctx, need_campaign=True, need_book=True, refresh_from_api=True
        )
        db_campaign = channel_objects.campaign
        db_book = channel_objects.book

        all_chapters = await chapters_service(
            user_id=api_user_id, campaign_id=db_campaign.api_id, book_id=db_book.api_id
        ).list_all()
        chapter = next((c for c in all_chapters if c.id == chapter_id), None)
        if not chapter:
            msg = "Chapter not found."
            raise exceptions.ValidationError(msg)

        if number <= 0 or number > len(all_chapters):
            msg = "The number must be greater than 0 and less than the number of chapters in the book."
            raise exceptions.ValidationError(msg)

        if number == chapter.number:
            msg = "The number is already the same as the current chapter number."
            raise exceptions.ValidationError(msg)

        title = f"Renumber Chapter: `{chapter.name}`"
        description = f"Are you sure you want to renumber the chapter to {number}?"
        is_confirmed, interaction, confirmation_embed = await confirm_action(
            ctx, title=title, description=description, hidden=hidden
        )
        if not is_confirmed:
            return

        await chapters_service(
            user_id=api_user_id, campaign_id=db_campaign.api_id, book_id=db_book.api_id
        ).renumber(chapter_id=chapter_id, number=number)

        confirmation_embed.description = "Chapter renumbered successfully."
        with contextlib.suppress(discord.errors.HTTPException):
            await interaction.edit_original_response(embed=confirmation_embed, view=None)

    @chapter.command(name="view", description="View a chapter")
    async def campaign_chapter_view(
        self,
        ctx: ValentinaContext,
        chapter_id: Annotated[
            str,
            Option(
                autocomplete=autocompletion.select_chapter,
                name="chapter_id",
                description="The ID of the chapter to view.",
                required=True,
            ),
        ],
        hidden: Annotated[
            bool,
            Option(
                name="hidden",
                description="Make the response visible only to you (default true).",
                required=False,
                default=True,
            ),
        ],
    ) -> None:
        """View a chapter."""
        api_user_id = await ctx.get_api_user_id()
        channel_objects = await fetch_channel_object(
            ctx, need_campaign=True, need_book=True, refresh_from_api=True
        )
        db_campaign = channel_objects.campaign
        db_book = channel_objects.book

        chapter_dto = await chapters_service(
            user_id=api_user_id, campaign_id=db_campaign.api_id, book_id=db_book.api_id
        ).get(chapter_id)

        text = f"## {chapter_dto.name}\n"
        text += f"{chapter_dto.description}\n" if chapter_dto.description else "\n"

        await auto_paginate(
            ctx,
            title="",
            text=text,
            color=EmbedColor.INFO,
            hidden=hidden,
            max_chars=900,
        )


def setup(bot: Valentina) -> None:
    """Register the cog with the bot.

    Initialize and add the cog to the Discord bot's extension system.
    This function is called automatically by the bot's extension loader.

    Args:
        bot (Valentina): The bot instance to register the cog with.
    """
    bot.add_cog(CampaignCog(bot))
