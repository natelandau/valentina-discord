"""Character cog."""

from io import BytesIO
from pathlib import Path
from typing import Annotated, get_args

import discord
import inflect
from discord.commands import Option
from discord.ext import commands
from vclient import character_traits_service, characters_service, companies_service
from vclient.constants import CharacterInventoryType, CharacterStatus
from vclient.models import (
    InventoryItemCreate,
    InventoryItemUpdate,
    NoteCreate,
    NoteUpdate,
    TraitCreate,
)

from vbot.bot import Valentina, ValentinaContext
from vbot.cogs import autocompletion, validators
from vbot.config.base import settings
from vbot.constants import VALID_IMAGE_EXTENSIONS, EmbedColor, EmojiDict
from vbot.db.models import DBCampaign
from vbot.handlers import character_handler
from vbot.lib.channel_mngr import ChannelManager
from vbot.lib.validation import get_valid_linked_db_user
from vbot.utils import fetch_channel_object, fetch_data_from_url, truncate_string
from vbot.views import (
    CharacterInventoryItemModal,
    CharacterNameBioModal,
    NoteModal,
    auto_paginate,
    present_embed,
)
from vbot.workflows import (
    AssetReviewHandler,
    CharacterAutogenerationHandler,
    CharacterManualEntryHandler,
    confirm_action,
    display_full_character_sheet,
)

p = inflect.engine()


class CharacterCog(commands.Cog):
    """Character cog."""

    def __init__(self, bot: Valentina):
        self.bot = bot

    character = discord.SlashCommandGroup(name="character", description="Manage characters")
    create = character.create_subgroup("create", "Create a new character")
    trait = character.create_subgroup("trait", "Work with character traits")
    image = character.create_subgroup("image", "Work with character images")
    inventory = character.create_subgroup("inventory", "Work with character inventory")
    note = character.create_subgroup("note", "Work with character notes")
    admin = character.create_subgroup("admin", "Work with character administration")

    @character.command(name="list", description="List all characters")
    async def character_list(
        self,
        ctx: ValentinaContext,
        scope: Annotated[
            str,
            Option(
                description="Scope of characters to list",
                default="all",
                choices=["all", "mine"],
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
        """List all characters."""
        channel_objects = await fetch_channel_object(ctx, need_campaign=True)
        db_campaign = channel_objects.campaign
        user_api_id = await ctx.get_api_user_id()

        character_dtos = await character_handler.list_characters(
            campaign_api_id=db_campaign.api_id,
            user_api_id=user_api_id,
            user_player_id=user_api_id if scope == "mine" else None,
        )

        if len(character_dtos) == 0:
            await present_embed(
                ctx,
                title="No Characters",
                description="There are no characters.\nCreate one with `/character create`",
                level="warning",
                ephemeral=hidden,
            )
            return

        title_prefix = "All" if scope == "all" else "Your"
        text = f"## {title_prefix} {p.plural_noun('character', len(character_dtos))} in `{db_campaign.name}`\n"
        for character_dto in sorted(character_dtos, key=lambda x: x.name):
            dead_emoji = EmojiDict.DEAD if character_dto.status != "ALIVE" else ""

            text += f"- {dead_emoji} **{character_dto.name}** _({character_dto.character_class.title()})_\n"

        await auto_paginate(
            ctx=ctx,
            title="",
            text=text,
            color=EmbedColor.INFO,
            hidden=hidden,
            max_chars=900,
        )

    @character.command(name="status", description="Update a character's status (Alive or Dead)")
    async def character_status(
        self,
        ctx: ValentinaContext,
        status: Annotated[
            str,
            Option(
                description="The status to set.",
                required=True,
                choices=list(get_args(CharacterStatus)),
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
        """Kill a character."""
        channel_objects = await fetch_channel_object(
            ctx, need_character=True, refresh_from_api=True
        )
        db_character = channel_objects.character

        if db_character.status == status:
            await present_embed(
                ctx,
                title="Character is already in that status",
                description=f"Character is already {status.lower()}.",
                level="warning",
                ephemeral=hidden,
            )
            return

        title = f"Change status of `{db_character.name}` to {status.lower()}"
        is_confirmed, msg, confirmation_embed = await confirm_action(
            ctx=ctx, title=title, hidden=hidden
        )
        if not is_confirmed:
            return

        if status not in get_args(CharacterStatus):
            await present_embed(
                ctx,
                title="Invalid status",
                description="The status is not valid.",
                level="error",
                ephemeral=hidden,
            )
            return

        await character_handler.update_character(
            ctx=ctx,
            campaign_api_id=db_character.campaign.api_id,
            character_api_id=db_character.api_id,
            status=status,  # type: ignore [arg-type]
        )

        confirmation_embed.description = f"Character is now {status.lower()}."
        await msg.edit_original_response(embed=confirmation_embed, view=None)

    @character.command(name="view", description="View a character sheet")
    async def character_view(
        self,
        ctx: ValentinaContext,
        character_api_id: Annotated[
            str,
            Option(
                autocomplete=autocompletion.select_player_character,
                name="character",
                description="The character to view.",
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
        """View a character sheet."""
        channel_objects = await fetch_channel_object(ctx, need_campaign=True)
        db_campaign = channel_objects.campaign

        character_dto = await character_handler.get_character(
            user_api_id=await ctx.get_api_user_id(),
            campaign_api_id=db_campaign.api_id,
            character_api_id=character_api_id,
        )

        await display_full_character_sheet(ctx, character=character_dto, ephemeral=hidden)

    @character.command(name="edit", description="Edit a character")
    async def character_edit(
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
        """Edit a character."""
        channel_objects = await fetch_channel_object(ctx, need_character=True)
        character = channel_objects.character
        character_dto = await character_handler.get_character(
            user_api_id=await ctx.get_api_user_id(),
            campaign_api_id=character.campaign.api_id,
            character_api_id=character.api_id,
        )

        modal = CharacterNameBioModal(
            title=truncate_string(f"Edit {character.name}", 45), existing_object=character_dto
        )
        await ctx.send_modal(modal)
        await modal.wait()
        if not modal.confirmed:
            return

        patched_character_dto = await character_handler.update_character(
            ctx=ctx,
            campaign_api_id=character.campaign.api_id,
            character_api_id=character.api_id,
            name_first=modal.name_first,
            name_last=modal.name_last,
            name_nick=modal.name_nick,
            biography=modal.biography,
        )

        await present_embed(
            ctx,
            title=f"Edit Character: `{patched_character_dto.name}`",
            level="success",
            description="Character updated successfully.",
            ephemeral=hidden,
            inline_fields=True,
        )

    ## CREATION ##############################################################
    @create.command(name="autogenerate", description="Autogenerate a new character")
    async def character_autogenerate(
        self,
        ctx: ValentinaContext,
    ) -> None:
        """Autogenerate a new character."""
        channel_objects = await fetch_channel_object(ctx, need_campaign=True)
        db_campaign = channel_objects.campaign
        company_dto = await companies_service().get(settings.api.default_company_id)
        api_user_id = await ctx.get_api_user_id()

        chargen_wizard = CharacterAutogenerationHandler(
            ctx=ctx,
            company_dto=company_dto,
            user_api_id=api_user_id,
            campaign_api_id=db_campaign.api_id,
        )
        await chargen_wizard.start()

    @create.command(name="manual", description="Create a new character manually")
    async def character_create_manual(
        self,
        ctx: ValentinaContext,
    ) -> None:
        """Create a new character manually."""
        ## GET CHANNEL OBJECTS #########
        channel_objects = await fetch_channel_object(ctx, need_campaign=True)
        db_campaign = channel_objects.campaign
        api_user_id = await ctx.get_api_user_id()

        manual_entry_wizard = CharacterManualEntryHandler(ctx, db_campaign, api_user_id)
        await manual_entry_wizard.start()

    ## TRAITS ##############################################################
    @trait.command(name="create", description="Create a new trait")
    async def trait_create(
        self,
        ctx: ValentinaContext,
        name: Annotated[
            str, Option(name="name", description="Name of of trait to add.", required=True)
        ],
        trait_category_api_id: Annotated[
            str,
            Option(
                autocomplete=autocompletion.select_trait_category,
                name="category",
                description="The category to create the trait in.",
                required=True,
            ),
        ],
        value: Option(int, "The value of the trait", required=True, min_value=0, max_value=20),  # type: ignore [valid-type]
        max_value: Option(  # type: ignore [valid-type]
            int,
            "The maximum value of the trait (Defaults to 5)",
            required=False,
            min_value=1,
            max_value=20,
            default=5,
        ),
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
        """Create a custom trait for a character."""
        channel_objects = await fetch_channel_object(ctx, need_character=True)
        character = channel_objects.character
        await character.fetch_related("campaign")

        api_user_id = await ctx.get_api_user_id()

        title = f"Add trait: `{name.title()}` at `{value}` dots for {character.name}"
        is_confirmed, msg, confirmation_embed = await confirm_action(
            ctx=ctx, title=title, hidden=hidden
        )
        if not is_confirmed:
            return

        await character_traits_service(
            user_id=api_user_id,
            character_id=character.api_id,
            campaign_id=character.campaign.api_id,
        ).create(
            request=TraitCreate(
                name=name,
                value=value,
                max_value=max_value,
                parent_category_id=trait_category_api_id,
            )
        )

        await msg.edit_original_response(embed=confirmation_embed, view=None)

    @trait.command(name="delete", description="Delete a trait from a character")
    async def trait_delete(
        self,
        ctx: ValentinaContext,
        trait_api_id: Annotated[
            str,
            Option(
                autocomplete=autocompletion.select_character_trait,
                name="trait",
                description="The trait to delete.",
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
        """Delete a trait."""
        channel_objects = await fetch_channel_object(ctx, need_character=True)
        character = channel_objects.character
        campaign = channel_objects.campaign
        api_user_id = await ctx.get_api_user_id()

        character_trait = await character_traits_service(
            user_id=api_user_id,
            character_id=character.api_id,
            campaign_id=campaign.api_id,
        ).get(trait_api_id)

        title = f"Delete {character_trait.trait.name} from {character.name}"
        description = f"This is a destructive action and will delete the trait `{character_trait.trait.name}` from {character.name} irreversibly."
        is_confirmed, msg, confirmation_embed = await confirm_action(
            ctx=ctx, title=title, description=description, hidden=hidden
        )
        if not is_confirmed:
            return

        await character_traits_service(
            user_id=api_user_id,
            character_id=character.api_id,
            campaign_id=campaign.api_id,
        ).delete(character_trait.id)

        confirmation_embed.description = (
            f"Trait `{character_trait.trait.name}` deleted successfully."
        )
        await msg.edit_original_response(embed=confirmation_embed, view=None)

    ## INVENTORY ##############################################################
    @inventory.command(name="create", description="Create a new inventory")
    async def inventory_create(
        self,
        ctx: ValentinaContext,
        item_name: Annotated[
            str, Option(name="name", description="Name of of inventory item to add.", required=True)
        ],
        item_type: Annotated[
            str,
            Option(
                name="type",
                description="Type of of inventory item to add.",
                required=True,
                choices=list(get_args(CharacterInventoryType)),
            ),
        ],
        item_description: Annotated[
            str,
            Option(
                name="description",
                description="Description of of inventory item to add.",
                required=False,
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
        """Create a new inventory item for a character."""
        channel_objects = await fetch_channel_object(ctx, need_character=True)
        character = channel_objects.character
        api_user_id = await ctx.get_api_user_id()

        title = f"Add inventory item: `{item_name.title()}` to {character.name}"
        is_confirmed, msg, confirmation_embed = await confirm_action(
            ctx=ctx, title=title, hidden=hidden
        )
        if not is_confirmed:
            return

        await character.fetch_related("campaign")

        if item_type not in get_args(CharacterInventoryType):
            await present_embed(
                ctx,
                title="Invalid inventory type",
                description="The inventory type is not valid.",
                level="error",
                ephemeral=hidden,
            )
            return

        inventory_item_dto = await characters_service(
            user_id=api_user_id,
            campaign_id=character.campaign.api_id,
        ).create_inventory_item(
            character_id=character.api_id,
            request=InventoryItemCreate(
                name=item_name,
                description=item_description,
                type=item_type,  # type: ignore [arg-type]
            ),
        )

        confirmation_embed.description = (
            f"Inventory item `{inventory_item_dto.name}` created successfully."
        )
        await msg.edit_original_response(embed=confirmation_embed, view=None)

    @inventory.command(name="delete", description="Delete an inventory item")
    async def inventory_delete(
        self,
        ctx: ValentinaContext,
        inventory_item_api_id: Annotated[
            str,
            Option(
                autocomplete=autocompletion.select_inventory_item,
                name="item",
                description="The inventory item to delete.",
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
        """Delete an inventory item."""
        channel_objects = await fetch_channel_object(ctx, need_character=True)
        character = channel_objects.character
        api_user_id = await ctx.get_api_user_id()

        selected_item = await characters_service(
            user_id=api_user_id,
            campaign_id=character.campaign.api_id,
        ).get_inventory_item(character_id=character.api_id, item_id=inventory_item_api_id)

        title = f"Delete inventory item: `{selected_item.name}` from {character.name}"
        description = f"This is a destructive action and will delete the inventory item `{selected_item.name}` from {character.name} irreversibly."
        is_confirmed, msg, confirmation_embed = await confirm_action(
            ctx=ctx, title=title, description=description, hidden=hidden
        )
        if not is_confirmed:
            return

        await characters_service(
            user_id=api_user_id,
            campaign_id=character.campaign.api_id,
        ).delete_inventory_item(character_id=character.api_id, item_id=selected_item.id)

        confirmation_embed.description = (
            f"Inventory item `{selected_item.name}` deleted successfully."
        )
        await msg.edit_original_response(embed=confirmation_embed, view=None)

    @inventory.command(name="edit", description="Edit an inventory item")
    async def inventory_edit(
        self,
        ctx: ValentinaContext,
        inventory_item_api_id: Annotated[
            str,
            Option(
                autocomplete=autocompletion.select_inventory_item,
                name="item",
                description="The inventory item to edit.",
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
        """Edit an inventory item."""
        channel_objects = await fetch_channel_object(ctx, need_character=True)
        character = channel_objects.character
        api_user_id = await ctx.get_api_user_id()

        selected_item = await characters_service(
            user_id=api_user_id,
            campaign_id=character.campaign.api_id,
        ).get_inventory_item(character_id=character.api_id, item_id=inventory_item_api_id)

        modal = CharacterInventoryItemModal(
            title=truncate_string(f"Edit {selected_item.name}", 45),
            existing_object=selected_item,
        )
        await ctx.send_modal(modal)
        await modal.wait()
        if not modal.confirmed:
            return

        modal_data = {
            "name": modal.name,
            "description": modal.description,
        }
        patch_data = {k: v for k, v in modal_data.items() if selected_item.model_dump()[k] != v}

        if not patch_data:
            await present_embed(
                ctx,
                title="No changes to apply",
                description="No changes to apply.",
                level="warning",
                ephemeral=hidden,
            )
            return

        patched_item = await characters_service(
            user_id=api_user_id,
            campaign_id=character.campaign.api_id,
        ).update_inventory_item(
            character_id=character.api_id,
            item_id=selected_item.id,
            request=InventoryItemUpdate(
                name=modal.name,
                description=modal.description,
            ),
        )
        await present_embed(
            ctx,
            title=f"Edit Inventory Item: `{patched_item.name}`",
            level="success",
            description="Inventory item updated successfully.",
            ephemeral=hidden,
            inline_fields=True,
        )

    ## NOTES ##############################################################
    @note.command(name="create", description="Create a new note")
    async def notes_create(
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
        """Create a new note for a character."""
        channel_objects = await fetch_channel_object(ctx, need_character=True, need_campaign=True)
        db_character = channel_objects.character
        db_campaign = channel_objects.campaign
        api_user_id = await ctx.get_api_user_id()

        modal = NoteModal(
            title=truncate_string("Create Note", 45),
            existing_object=None,
        )
        await ctx.send_modal(modal)
        await modal.wait()
        if not modal.confirmed:
            return

        note = await characters_service(
            user_id=api_user_id,
            campaign_id=db_campaign.api_id,
        ).create_note(
            character_id=db_character.api_id,
            request=NoteCreate(
                title=modal.note_title,
                content=modal.content,
            ),
        )

        await present_embed(
            ctx,
            title=f"Create Note: `{note.title}`",
            level="success",
            description="Note created successfully.",
            ephemeral=hidden,
            inline_fields=True,
        )

    @note.command(name="edit", description="Edit a note")
    async def notes_edit(
        self,
        ctx: ValentinaContext,
        note_api_id: Annotated[
            str,
            Option(
                autocomplete=autocompletion.select_note,
                name="note",
                description="The note to edit.",
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
        """Edit a note for a character."""
        channel_objects = await fetch_channel_object(ctx, need_character=True)
        character = channel_objects.character
        api_user_id = await ctx.get_api_user_id()

        selected_note = await characters_service(
            user_id=api_user_id,
            campaign_id=character.campaign.api_id,
        ).get_note(character_id=character.api_id, note_id=note_api_id)

        modal = NoteModal(
            title=truncate_string(f"Edit {selected_note.title}", 45),
            existing_object=selected_note,
        )
        await ctx.send_modal(modal)
        await modal.wait()
        if not modal.confirmed:
            return

        if modal.title == selected_note.title and modal.content == selected_note.content:
            await present_embed(
                ctx,
                title="No changes to apply",
                description="No changes to apply.",
                level="warning",
                ephemeral=hidden,
            )
            return

        patched_note = await characters_service(
            user_id=api_user_id,
            campaign_id=character.campaign.api_id,
        ).update_note(
            character_id=character.api_id,
            note_id=selected_note.id,
            request=NoteUpdate(
                title=modal.note_title,
                content=modal.content,
            ),
        )

        await present_embed(
            ctx,
            title=f"Edit Note: `{patched_note.title}`",
            level="success",
            description="Note updated successfully.",
            ephemeral=hidden,
            inline_fields=True,
        )

    @note.command(name="delete", description="Delete a note")
    async def notes_delete(
        self,
        ctx: ValentinaContext,
        note_api_id: Annotated[
            str,
            Option(
                autocomplete=autocompletion.select_note,
                name="note",
                description="The note to delete.",
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
        """Delete a note for a character."""
        channel_objects = await fetch_channel_object(ctx, need_character=True)
        character = channel_objects.character
        api_user_id = await ctx.get_api_user_id()

        selected_note = await characters_service(
            user_id=api_user_id,
            campaign_id=character.campaign.api_id,
        ).get_note(character_id=character.api_id, note_id=note_api_id)

        title = f"Delete note: `{selected_note.title}` from {character.name}"
        description = f"This is a destructive action and will delete the note `{selected_note.title}` from {character.name} irreversibly."
        is_confirmed, msg, confirmation_embed = await confirm_action(
            ctx=ctx, title=title, description=description, hidden=hidden
        )
        if not is_confirmed:
            return

        await characters_service(
            user_id=api_user_id,
            campaign_id=character.campaign.api_id,
        ).delete_note(character_id=character.api_id, note_id=selected_note.id)

        confirmation_embed.description = f"Note `{selected_note.title}` deleted successfully."
        await msg.edit_original_response(embed=confirmation_embed, view=None)

    ## ASSETS ##############################################################

    @image.command(name="add", description="Add an image to a character")
    async def character_image_add(
        self,
        ctx: ValentinaContext,
        file: Option(  # type: ignore [valid-type]
            discord.Attachment,
            description="Location of the image on your local computer",
            required=False,
            default=None,
        ),
        url: Option(  # type: ignore [valid-type]
            validators.ValidImageURL,
            description="URL of the thumbnail",
            required=False,
            default=None,
        ),
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
        """Add an image to a character."""
        channel_objects = await fetch_channel_object(ctx, need_character=True)
        character = channel_objects.character
        api_user_id = await ctx.get_api_user_id()

        if (not file and not url) or (file and url):
            await present_embed(ctx, title="Provide a single image", level="error")
            return

        if file:
            file_extension = Path(file.filename).suffix.lstrip(".").lower()
            file_name = Path(file.filename).stem

            if file_extension not in VALID_IMAGE_EXTENSIONS:
                await present_embed(
                    ctx,
                    title=f"Must provide a valid image: {', '.join(VALID_IMAGE_EXTENSIONS)}",
                    level="error",
                )
                return
            file_bytes = await file.read()
            file_data_embed = BytesIO(file_bytes)

        else:
            file_extension = url.split(".")[-1].lower()
            file_name = url.split("/")[-1].split(".")[0]
            url_data = await fetch_data_from_url(url)
            file_bytes = url_data.getvalue()
            file_data_embed = BytesIO(file_bytes)

        title = f"Add this image to `{character.name}`"
        is_confirmed, msg, confirmation_embed = await confirm_action(
            ctx=ctx,
            title=title,
            hidden=hidden,
            file=discord.File(file_data_embed, filename=f"{file_name}.{file_extension}"),
        )
        if not is_confirmed:
            return

        await characters_service(
            user_id=api_user_id,
            campaign_id=character.campaign.api_id,
        ).upload_asset(
            character_id=character.api_id,
            content=file_bytes,
            filename=f"{file_name}.{file_extension}",
            content_type=f"image/{file_extension}",
        )

        confirmation_embed.description = "Image added successfully."
        await msg.edit_original_response(embed=confirmation_embed, view=None)

    @image.command(name="review", description="Review images for a character")
    async def character_image_review(
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
        """Review images for a character."""
        channel_objects = await fetch_channel_object(ctx, need_character=True)
        character = channel_objects.character
        api_user_id = await ctx.get_api_user_id()

        assets = await characters_service(
            user_id=api_user_id,
            campaign_id=character.campaign.api_id,
        ).list_all_assets(character_id=character.api_id)

        await AssetReviewHandler(ctx=ctx, assets=assets, hidden=hidden).send()

    ## ADMIN ##############################################################
    @admin.command(name="transfer", description="Transfer a character to a new user")
    async def admin_transfer(
        self,
        ctx: ValentinaContext,
        new_owner: Option(discord.User, description="The user to transfer the character to"),  # type: ignore [valid-type]
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
        """Transfer a character to a new user."""
        channel_objects = await fetch_channel_object(ctx, need_character=True)
        character = channel_objects.character
        campaign = channel_objects.campaign
        api_user_id = await ctx.get_api_user_id()

        if new_owner == ctx.author:
            await present_embed(
                ctx,
                title="Cannot transfer to yourself",
                description="You cannot transfer a character to yourself",
                level="error",
                ephemeral=hidden,
            )
            return

        db_new_owner = await get_valid_linked_db_user(new_owner)
        db_current_owner = await get_valid_linked_db_user(ctx.author)

        title = f"Transfer character: `{character.name}` to {new_owner.display_name}"
        description = f"This action will transfer the character `{character.name}` from `{db_current_owner.name}` to `{new_owner.display_name}`."
        is_confirmed, msg, confirmation_embed = await confirm_action(
            ctx=ctx, title=title, description=description, hidden=hidden
        )
        if not is_confirmed:
            return

        updated_character = await characters_service(
            user_id=api_user_id,
            campaign_id=campaign.api_id,
        ).update(
            character_id=character.api_id,
            user_player_id=db_new_owner.api_user_id,
        )
        await character_handler.update_or_create_character_in_db(updated_character)

        confirmation_embed.description = f"Character `{character.name}` transferred from `{db_current_owner.name}` to `{new_owner.display_name}` successfully."
        await msg.edit_original_response(embed=confirmation_embed, view=None)

    @admin.command(name="delete", description="Delete a character")
    async def admin_delete(
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
        """Delete a character."""
        channel_objects = await fetch_channel_object(ctx, need_character=True)
        character = channel_objects.character
        api_user_id = await ctx.get_api_user_id()

        title = f"Delete character: `{character.name}`"
        description = f"This is a destructive action and will delete the character `{character.name}` irreversibly."
        is_confirmed, msg, confirmation_embed = await confirm_action(
            ctx=ctx, title=title, description=description, hidden=hidden
        )
        if not is_confirmed:
            return

        await character_handler.delete_character(
            ctx=ctx,
            user_api_id=api_user_id,
            campaign_api_id=character.campaign.api_id,
            character_api_id=character.api_id,
        )

        confirmation_embed.description = f"Character `{character.name}` deleted successfully."
        await msg.edit_original_response(embed=confirmation_embed, view=None)

    @admin.command(name="transfer-campaign", description="Transfer a character to a new campaign")
    async def admin_transfer_campaign(
        self,
        ctx: ValentinaContext,
        campaign_api_id: Annotated[
            str,
            Option(
                autocomplete=autocompletion.select_campaign,
                name="campaign",
                description="The campaign to transfer the character to.",
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
        """Transfer a character to a new campaign."""
        channel_objects = await fetch_channel_object(ctx, need_character=True)
        character = channel_objects.character
        current_campaign = channel_objects.campaign
        new_campaign = await DBCampaign.get(api_id=campaign_api_id)
        api_user_id = await ctx.get_api_user_id()

        if new_campaign == current_campaign:
            await present_embed(
                ctx,
                title="Cannot transfer to the same campaign",
                description="You cannot transfer a character to the same campaign",
                level="error",
                ephemeral=hidden,
            )
            return

        title = f"Transfer character: `{character.name}` to {new_campaign.name}"
        description = f"This action will transfer the character `{character.name}` from `{current_campaign.name}` to `{new_campaign.name}`."
        is_confirmed, msg, confirmation_embed = await confirm_action(
            ctx=ctx, title=title, description=description, hidden=hidden
        )
        if not is_confirmed:
            return

        await characters_service(
            user_id=api_user_id,
            campaign_id=current_campaign.api_id,
        ).update(
            character_id=character.api_id,
            campaign_id=new_campaign.api_id,
        )
        confirmation_embed.description = f"Character `{character.name}` transferred from `{current_campaign.name}` to `{new_campaign.name}` successfully."
        await msg.edit_original_response(embed=confirmation_embed, view=None)

        channel_manager = ChannelManager(guild=ctx.guild)
        await channel_manager.delete_character_channel(character=character)
        await channel_manager.confirm_character_channel(character=character, campaign=new_campaign)
        await channel_manager.sort_campaign_channels(new_campaign)


def setup(bot: Valentina) -> None:
    """Register the cog with the bot.

    Initialize and add the cog to the Discord bot's extension system.
    This function is called automatically by the bot's extension loader.

    Args:
        bot (Valentina): The bot instance to register the cog with.
    """
    bot.add_cog(CharacterCog(bot))
