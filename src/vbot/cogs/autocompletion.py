"""Shared autocompletions for all cogs."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import inflect
from discord import OptionChoice
from vclient import (
    chapters_service,
    character_blueprint_service,
    character_traits_service,
    characters_service,
    users_service,
)

from vbot.constants import MAX_OPTION_LIST_SIZE, EmojiDict
from vbot.handlers import campaign_handler, character_handler
from vbot.utils.discord import fetch_channel_object

if TYPE_CHECKING:
    from vclient.models import TraitCategory

    from vbot.bot import ValentinaAutocompleteContext


async def select_any_trait(ctx: ValentinaAutocompleteContext) -> list[OptionChoice]:
    """Select a trait from the list of traits."""
    all_constant_traits = await character_blueprint_service().list_all_traits()

    if ctx.options.get("trait_one"):
        bson_id_regex = re.compile(r"^[0-9a-fA-F]{24}$")
        if bson_id_regex.match(ctx.options.get("trait_one")):
            del ctx.options["trait_one"]

    argument = (
        ctx.options.get("trait")
        or ctx.options.get("trait_one")
        or ctx.options.get("trait_two")
        or ""
    )

    return [
        OptionChoice(trait.name.title(), str(trait.id))
        for trait in all_constant_traits
        if trait.name.lower().startswith(argument.lower())
    ][:MAX_OPTION_LIST_SIZE]


async def select_any_trait_for_character(ctx: ValentinaAutocompleteContext) -> list[OptionChoice]:
    """Select a trait from the list of traits for a character from the character blueprint service."""
    channel_objects = await fetch_channel_object(ctx, need_character=True)
    db_character = channel_objects.character

    character = await character_handler.get_character(
        user_api_id=await ctx.get_api_user_id(),
        campaign_api_id=db_character.campaign.api_id,
        character_api_id=db_character.api_id,
    )

    all_constant_traits = await character_blueprint_service().list_all_traits(
        character_class=character.character_class, game_version=character.game_version
    )

    argument = ctx.options.get("trait") or ""
    return [
        OptionChoice(trait.name.title(), str(trait.id))
        for trait in all_constant_traits
        if trait.name.lower().startswith(argument.lower())
    ][:MAX_OPTION_LIST_SIZE]


async def select_campaign(ctx: ValentinaAutocompleteContext) -> list[OptionChoice]:
    """Select a campaign from the list of campaigns."""
    api_user_id = await ctx.get_api_user_id()

    argument = ctx.options.get("campaign") or ""

    campaigns = await campaign_handler.list_campaigns(user_api_id=api_user_id)
    return [
        OptionChoice(campaign.name, str(campaign.id))
        for campaign in sorted(campaigns, key=lambda x: x.name)
        if campaign.name.lower().startswith(argument.lower())
    ][:MAX_OPTION_LIST_SIZE]


async def select_chapter(ctx: ValentinaAutocompleteContext) -> list[OptionChoice]:
    """Select a chapter from the list of chapters."""
    api_user_id = await ctx.get_api_user_id()
    channel_objects = await fetch_channel_object(ctx, raise_error=False)
    book = channel_objects.book
    if not book:
        return [OptionChoice("Not in book channel", "")]

    await book.fetch_related("campaign")

    argument = ctx.options.get("chapter") or ""

    chapters = await chapters_service(
        user_id=api_user_id, campaign_id=book.campaign.api_id, book_id=book.api_id
    ).list_all()
    choices = [
        OptionChoice(f"{chapter.number}. {chapter.name}", str(chapter.id))
        for chapter in sorted(chapters, key=lambda x: x.number)
        if chapter.name.lower().startswith(argument.lower())
    ][:MAX_OPTION_LIST_SIZE]

    return choices or [OptionChoice("No chapters", "")]


async def select_character_trait(ctx: ValentinaAutocompleteContext) -> list[OptionChoice]:
    """Select a trait from the list of traits for a character."""
    channel_objects = await fetch_channel_object(ctx, need_character=True)
    character = channel_objects.character
    await character.fetch_related("campaign")
    api_user_id = await ctx.get_api_user_id()

    if ctx.options.get("trait_one"):
        bson_id_regex = re.compile(r"^[0-9a-fA-F]{24}$")
        if bson_id_regex.match(ctx.options.get("trait_one")):
            del ctx.options["trait_one"]

    argument = (
        ctx.options.get("trait")
        or ctx.options.get("trait_one")
        or ctx.options.get("trait_two")
        or ""
    )

    character_trait_dtos = await character_traits_service(
        user_id=api_user_id,
        character_id=character.api_id,
        campaign_id=character.campaign.api_id,
    ).list_all()

    return sorted(
        [
            OptionChoice(trait.trait.name, str(trait.id))
            for trait in character_trait_dtos
            if trait.trait.name.lower().startswith(argument.lower())
        ],
        key=lambda x: x.name,
    )[:MAX_OPTION_LIST_SIZE]


async def select_desperation_dice(ctx: ValentinaAutocompleteContext) -> list[OptionChoice]:
    """Select a desperation dice from the list of desperation dice."""
    p = inflect.engine()

    channel_objects = await fetch_channel_object(ctx, raise_error=False)
    campaign = channel_objects.campaign
    campaign_dto = await campaign_handler.get_campaign(
        user_api_id=await ctx.get_api_user_id(), campaign_api_id=campaign.api_id
    )

    if not campaign_dto:
        return [OptionChoice("No active campaign", "")]

    if campaign_dto.desperation == 0:
        return [OptionChoice("No desperation dice", "0")]

    return [
        OptionChoice(f"{p.number_to_words(i).capitalize()} {p.plural('die', i)}", i)  # type: ignore [arg-type, union-attr]
        for i in range(1, campaign_dto.desperation + 1)
    ]


async def select_inventory_item(ctx: ValentinaAutocompleteContext) -> list[OptionChoice]:
    """Select an inventory item from the list of inventory items."""
    channel_objects = await fetch_channel_object(ctx, need_character=True)
    character = channel_objects.character
    api_user_id = await ctx.get_api_user_id()

    argument = ctx.options.get("item") or ""

    inventory_item_dtos = await characters_service(
        user_id=api_user_id,
        campaign_id=character.campaign.api_id,
    ).list_all_inventory(character.api_id)

    return sorted(
        [
            OptionChoice(inventory_item.name, str(inventory_item.id))
            for inventory_item in inventory_item_dtos
            if inventory_item.name.lower().startswith(argument.lower())
        ],
        key=lambda x: x.name,
    )[:MAX_OPTION_LIST_SIZE]


async def select_note(ctx: ValentinaAutocompleteContext) -> list[OptionChoice]:
    """Select a character note from the list of notes."""
    channel_objects = await fetch_channel_object(ctx, need_character=True)
    character = channel_objects.character
    api_user_id = await ctx.get_api_user_id()

    argument = ctx.options.get("note") or ""

    note_dtos = await characters_service(
        user_id=api_user_id,
        campaign_id=character.campaign.api_id,
    ).list_all_notes(character.api_id)

    return sorted(
        [
            OptionChoice(note.title.title(), str(note.id))
            for note in note_dtos
            if note.title.lower().startswith(argument.lower())
        ],
        key=lambda x: x.name,
    )[:MAX_OPTION_LIST_SIZE]


async def select_player_character(ctx: ValentinaAutocompleteContext) -> list[OptionChoice]:
    """Select a player character from the list of the user's characters."""
    api_user_id = await ctx.get_api_user_id()
    channel_objects = await fetch_channel_object(ctx, need_campaign=True, raise_error=False)
    campaign_id = channel_objects.campaign.api_id

    player_character_dtos = await character_handler.list_characters(
        user_api_id=api_user_id,
        campaign_api_id=campaign_id,
        character_type="PLAYER",
    )

    options = [
        OptionChoice(
            f"{character.name}"
            if character.status == "ALIVE"
            else f"{EmojiDict.DEAD} {character.name}",
            str(character.id),
        )
        for character in sorted(player_character_dtos, key=lambda x: x.name)
        if character.name.lower().startswith(ctx.value.lower())
    ]

    return options[:MAX_OPTION_LIST_SIZE]


async def select_quick_roll(ctx: ValentinaAutocompleteContext) -> list[OptionChoice]:
    """Select a quick roll from the list of quick rolls."""
    api_user_id = await ctx.get_api_user_id()
    quick_rolls = await users_service().list_all_quickrolls(user_id=api_user_id)

    if not quick_rolls:
        return [OptionChoice("No quick rolls found.", "")]

    argument = ctx.options.get("quick_roll") or ""

    return [
        OptionChoice(quick_roll.name.title(), str(quick_roll.id))
        for quick_roll in sorted(quick_rolls, key=lambda x: x.name)
        if quick_roll.name.lower().startswith(argument.lower())
    ][:MAX_OPTION_LIST_SIZE]


async def select_storyteller_character(ctx: ValentinaAutocompleteContext) -> list[OptionChoice]:
    """Select a storyteller character from the list of the user's characters."""
    api_user_id = await ctx.get_api_user_id()
    channel_objects = await fetch_channel_object(ctx, need_campaign=True, raise_error=False)
    campaign_id = channel_objects.campaign.api_id

    storyteller_character_dtos = await character_handler.list_characters(
        user_api_id=api_user_id,
        campaign_api_id=campaign_id,
        character_type="STORYTELLER",
    )

    options = [
        OptionChoice(
            f"{character.name}"
            if character.status == "ALIVE"
            else f"{EmojiDict.DEAD} {character.name}",
            str(character.id),
        )
        for character in sorted(storyteller_character_dtos, key=lambda x: x.name)
        if character.name.lower().startswith(ctx.value.lower())
    ]

    return options[:MAX_OPTION_LIST_SIZE]


async def select_trait_category(ctx: ValentinaAutocompleteContext) -> list[OptionChoice]:
    """Select a trait category from the list of trait categories."""
    channel_objects = await fetch_channel_object(ctx, need_character=True)
    db_character = channel_objects.character
    character_dto = await character_handler.get_character(
        user_api_id=await ctx.get_api_user_id(),
        campaign_api_id=db_character.campaign.api_id,
        character_api_id=db_character.api_id,
    )

    sheet_sections = await character_blueprint_service().list_all_sections(
        game_version=character_dto.game_version,
    )

    trait_categories: list[TraitCategory] = []
    for section in sheet_sections:
        trait_categories.extend(
            await character_blueprint_service().list_all_categories(
                game_version=character_dto.game_version,
                section_id=section.id,
                character_class=character_dto.character_class,
            )
        )

    argument = ctx.options.get("category") or ""

    return sorted(
        [
            OptionChoice(trait_category.name, str(trait_category.id))
            for trait_category in trait_categories
            if trait_category.name.lower().startswith(argument.lower())
        ],
        key=lambda x: x.name,
    )[:MAX_OPTION_LIST_SIZE]
