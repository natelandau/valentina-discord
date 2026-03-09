"""Storyteller cog."""

from typing import Annotated

import discord
import inflect
from discord.commands import Option
from discord.ext import commands
from vclient import character_blueprint_service, character_traits_service
from vclient.exceptions import NotFoundError

from vbot.bot import Valentina, ValentinaContext
from vbot.cogs import autocompletion
from vbot.handlers import character_handler
from vbot.utils.discord import fetch_channel_object
from vbot.utils.strings import truncate_string
from vbot.views import CharacterNameBioModal, present_embed
from vbot.workflows import (
    CharacterManualEntryHandler,
    QuickCharacterGenerationHandler,
    confirm_action,
    display_full_character_sheet,
)

p = inflect.engine()


class StorytellerCog(commands.Cog):
    """Storyteller cog."""

    def __init__(self, bot: Valentina):
        self.bot = bot

    storyteller = discord.SlashCommandGroup(
        "storyteller",
        "Commands for the storyteller",
        checks=[commands.has_any_role("Storyteller", "Admin").predicate],  # type: ignore [attr-defined]
    )
    character = storyteller.create_subgroup(
        "character",
        "Work with storyteller characters",
        checks=[commands.has_any_role("Storyteller", "Admin").predicate],  # type: ignore [attr-defined]
    )
    player = storyteller.create_subgroup(
        "player",
        "Work with player characters",
        checks=[commands.has_any_role("Storyteller", "Admin").predicate],  # type: ignore [attr-defined]
    )
    roll = storyteller.create_subgroup(
        "roll",
        "Roll dice for storyteller characters",
        checks=[commands.has_any_role("Storyteller", "Admin").predicate],  # type: ignore [attr-defined]
    )

    ### CHARACTER COMMANDS ############################################

    @character.command(name="view", description="View a character sheet")
    async def character_view(
        self,
        ctx: ValentinaContext,
        character_api_id: Annotated[
            str,
            Option(
                autocomplete=autocompletion.select_storyteller_character,
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

    @character.command(
        name="create_full",
        description="Create a full npc character using the add from sheet wizard",
    )
    async def create_story_char(
        self,
        ctx: ValentinaContext,
    ) -> None:
        """Create a new storyteller character using the add from sheet wizard."""
        channel_objects = await fetch_channel_object(ctx, need_campaign=True)
        db_campaign = channel_objects.campaign
        api_user_id = await ctx.get_api_user_id()

        manual_entry_wizard = CharacterManualEntryHandler(
            ctx,
            db_campaign=db_campaign,
            api_user_id=api_user_id,
            character_type="STORYTELLER",
        )
        await manual_entry_wizard.start()

    @character.command(
        name="create_rng",
        description="Quick roll a new storyteller character using the add from sheet wizard",
    )
    async def create_rng_char(
        self,
        ctx: ValentinaContext,
    ) -> None:
        """Create a new storyteller character using the RNG wizard."""
        channel_objects = await fetch_channel_object(ctx, need_campaign=True)
        db_campaign = channel_objects.campaign
        api_user_id = await ctx.get_api_user_id()

        quick_gen_wizard = QuickCharacterGenerationHandler(
            ctx=ctx,
            db_campaign=db_campaign,
            api_user_id=api_user_id,
            character_type="STORYTELLER",
        )
        await quick_gen_wizard.start()

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

    @character.command(
        name="delete",
        description="Delete a storyteller character",
    )
    async def delete_story_char(
        self,
        ctx: ValentinaContext,
        character_api_id: Annotated[
            str,
            Option(
                autocomplete=autocompletion.select_storyteller_character,
                name="character",
                description="The character to delete",
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
        """Delete a storyteller character."""
        channel_objects = await fetch_channel_object(ctx, need_campaign=True)
        db_campaign = channel_objects.campaign
        api_user_id = await ctx.get_api_user_id()

        character = await character_handler.get_character(
            user_api_id=api_user_id,
            campaign_api_id=db_campaign.api_id,
            character_api_id=character_api_id,
        )

        title = f"Delete storyteller character: `{character.name}`"
        description = f"This is a destructive action and will delete the storyteller character `{character.name}` irreversibly."
        is_confirmed, msg, confirmation_embed = await confirm_action(
            ctx=ctx, title=title, description=description, hidden=hidden
        )
        if not is_confirmed:
            return

        await character_handler.delete_character(
            ctx=ctx,
            user_api_id=api_user_id,
            campaign_api_id=character.campaign_id,
            character_api_id=character.id,
        )

        confirmation_embed.description = (
            f"Storyteller character `{character.name}` deleted successfully."
        )
        await msg.edit_original_response(embed=confirmation_embed, view=None)

    @character.command(
        name="trait_update", description="Update a trait for a storyteller character"
    )
    async def trait_update(
        self,
        ctx: ValentinaContext,
        trait_api_id: Annotated[
            str,
            Option(
                autocomplete=autocompletion.select_any_trait_for_character,
                name="trait",
                description="The trait to update",
                required=True,
            ),
        ],
        new_value: Annotated[
            int,
            Option(int, description="The new value for the trait", required=True),
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
        """Update a trait for a storyteller character."""
        channel_objects = await fetch_channel_object(ctx, need_character=True)
        db_character = channel_objects.character
        await db_character.fetch_related("campaign")
        api_user_id = await ctx.get_api_user_id()

        trait = await character_blueprint_service().get_trait(trait_id=trait_api_id)

        if not trait.min_value <= new_value <= trait.max_value:
            await present_embed(
                ctx,
                title=f"Error: {trait.name} must be between {trait.min_value} and {trait.max_value}",
                description=f"The value of {trait.name} must be between {trait.min_value} and {trait.max_value}",
                level="error",
                ephemeral=True,
            )
            return

        title = f"Set `{trait.name}` to `{new_value}`"
        description = ""
        is_confirmed, msg, confirmation_embed = await confirm_action(
            ctx=ctx, title=title, description=description, hidden=hidden
        )
        if not is_confirmed:
            return

        try:
            existing_trait = await character_traits_service(
                user_id=api_user_id,
                character_id=db_character.api_id,
                campaign_id=db_character.campaign.api_id,
            ).get(trait_api_id)
        except NotFoundError:
            await character_traits_service(
                user_id=api_user_id,
                character_id=db_character.api_id,
                campaign_id=db_character.campaign.api_id,
            ).assign(
                trait_id=trait_api_id,
                value=new_value,
                currency="NO_COST",
            )
        else:
            await character_traits_service(
                user_id=api_user_id,
                character_id=db_character.api_id,
                campaign_id=db_character.campaign.api_id,
            ).change_value(
                character_trait_id=existing_trait.id,
                new_value=new_value,
                currency="NO_COST",
            )

        confirmation_embed.description = f"Trait `{trait.name}` updated successfully."
        await msg.edit_original_response(embed=confirmation_embed, view=None)


def setup(bot: Valentina) -> None:
    """Register the cog with the bot.

    Initialize and add the cog to the Discord bot's extension system.
    This function is called automatically by the bot's extension loader.

    Args:
        bot (Valentina): The bot instance to register the cog with.
    """
    bot.add_cog(StorytellerCog(bot))
