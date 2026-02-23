"""View for displaying a character sheet."""

# TODO: Add support for werwolf rites/gifts/edges/perks/etc.

from __future__ import annotations

from typing import TYPE_CHECKING, get_args

import discord
import humanize
from discord.ext import pages
from vclient import character_blueprint_service, characters_service
from vclient.constants import CharacterInventoryType

from vbot.constants import MAX_DOT_DISPLAY, EmbedColor
from vbot.lib.character_sheet_builder import CharacterSheetController, SheetSectionObject
from vbot.utils import get_discord_member_from_api_user_id, num_to_circles, time_now

if TYPE_CHECKING:
    from vclient.models import Asset, Character, InventoryItem, Note

    from vbot.bot import ValentinaContext

__all__ = ("display_full_character_sheet", "first_page_of_character_sheet_as_embed")


def _build_footer(character: Character, player_discord_member: discord.Member | None = None) -> str:
    """Builds the footer for a character sheet."""
    modified = humanize.naturaldelta(time_now() - character.date_modified) + " ago"

    footer = "---\n"
    footer += f"Played by: {player_discord_member.display_name} • " if player_discord_member else ""
    footer += f"Last updated: {modified}"
    return footer


async def __embed1(  # noqa: PLR0913
    character: Character,
    *,
    player_discord_member: discord.Member | None = None,
    profile_data: dict,
    trait_data: list[SheetSectionObject],
    title: str | None = None,
    description_prefix: str | None = None,
    description_suffix: str | None = None,
    show_footer: bool = True,
) -> discord.Embed:
    """Builds the first embed of a character sheet. This embed contains the character's name, class, experience, cool points, and attributes and abilities.

    Args:
        character (Character): The character to display.
        player_discord_member (discord.Member | None): The Discord member for the player.
        profile_data (dict): The profile data for the character.
        trait_data (list[SheetSectionObject]): The trait data for the character.
        title (str | None): The title of the embed.
        description_prefix (str | None): The prefix of the description.
        description_suffix (str | None): The suffix of the description.
        show_footer (bool): Whether to show the footer.
    """
    embed = discord.Embed(
        title=title or f"{character.name_full}",
        description=description_prefix,
        color=EmbedColor.INFO.value,
    )

    if show_footer:
        embed.set_footer(text=_build_footer(character, player_discord_member))

    for key, value in profile_data.items():
        embed.add_field(
            name=key,
            value=value,
        )

    for section in trait_data:
        embed.add_field(
            name="\u200b",
            value=f"**{section.section.name.upper()}**",
            inline=False,
        )
        for category in section.categories:
            trait_values = [
                f"`{x.trait.name:14}: {num_to_circles(x.value, x.trait.max_value)}`"
                if x.trait.max_value <= MAX_DOT_DISPLAY
                else f"`{x.trait.name:14}: {x.value}/{x.trait.max_value}`"
                for x in category.traits
            ]
            if trait_values:
                embed.add_field(
                    name=category.category.name.title(),
                    value="\n".join(trait_values),
                    inline=True,
                )

    if description_suffix:
        embed.add_field(name="\u200b", value=description_suffix, inline=False)

    return embed


async def __biography_inventory_embed(
    character: Character,
    *,
    title: str | None = None,
    show_footer: bool = True,
    player_discord_member: discord.Member | None = None,
    inventory_data: list[InventoryItem] = [],
) -> discord.Embed:
    """Builds the second embed of a character sheet. This embed contains the character's biography and inventory."""
    embed = discord.Embed(
        title=title or f"{character.name_full} - Page 2",
        description="",
        color=EmbedColor.INFO.value,
    )

    if show_footer:
        embed.set_footer(text=_build_footer(character, player_discord_member))

    if character.biography:
        embed.add_field(name="**BIOGRAPHY**", value=character.biography, inline=False)

    if inventory_data:
        embed.add_field(name="\u200b", value="**INVENTORY**", inline=False)
        for member in get_args(CharacterInventoryType):
            sub_items = [i for i in inventory_data if i.type == member]
            content = ""
            for i in sub_items:
                line_begin = "- "
                name = f"**{i.name}**"
                desc = f": {i.description}" if i.description else ""
                line_end = "\n"
                content += f"{line_begin}{name}{desc}{line_end}"

            if sub_items:
                embed.add_field(name=f"__**{member.title()}**__", value=content, inline=False)
    else:
        embed.add_field(name="**EMPTY INVENTORY**", value="No items in inventory", inline=False)

    return embed


async def __notes_embed(
    character: Character,
    *,
    title: str | None = None,
    show_footer: bool = True,
    player_discord_member: discord.Member | None = None,
    notes: list[Note] = [],
) -> discord.Embed:
    """Builds the notes embed of a character sheet."""
    description = (
        "\n".join([f"### {note.title}\n{note.content}\n" for note in notes])
        if notes
        else "No notes"
    )

    embed = discord.Embed(
        title=title or f"{character.name_full} - Page 3",
        description=description,
        color=EmbedColor.INFO.value,
    )

    if show_footer:
        embed.set_footer(text=_build_footer(character, player_discord_member))

    return embed


def __image_embed(
    character: Character,
    *,
    asset: Asset,
    player_discord_member: discord.Member | None = None,
    title: str | None = None,
    show_footer: bool = True,
) -> discord.Embed:
    """Builds the second embed of a character sheet. This embed contains the character's bio and custom sections."""
    if title is None:
        title = f"{character.name_full} - Images"

    embed = discord.Embed(title=title, description="", color=0x7777FF)

    if show_footer:
        embed.set_footer(text=_build_footer(character, player_discord_member))

    embed.set_image(url=asset.public_url)

    return embed


async def display_full_character_sheet(
    ctx: ValentinaContext,
    *,
    character: Character,
    ephemeral: bool = False,
    show_footer: bool = True,
    description_prefix: str | None = None,
    description_suffix: str | None = None,
) -> None:
    """Show a character sheet.

    Args:
        ctx (ValentinaContext): The context containing the guild.
        character (Character): The character to display.
        ephemeral (bool): Whether to make the response ephemeral.
        show_footer (bool): Whether to show the footer.
        description_prefix (str | None): The prefix of the description.
        description_suffix (str | None): The suffix of the description.

    Returns:
        None
    """
    api_user_id = await ctx.get_api_user_id()
    sheet_builder = CharacterSheetController(ctx=ctx, character=character)
    # permission_mng = PermissionManager(ctx.guild.id)  # noqa: ERA001
    # is_storyteller = await permission_mng.is_storyteller(ctx.author.id)  # noqa: ERA001

    player_discord_member = await get_discord_member_from_api_user_id(
        ctx=ctx, api_user_id=character.user_player_id
    )
    concept_dto = (
        await character_blueprint_service().get_concept(concept_id=character.concept_id)
        if character.concept_id
        else None
    )

    profile_data = await sheet_builder.build_profile(
        player_discord_member=player_discord_member,
        concept_dto=concept_dto,
        storyteller_view=False,  # TODO: Add storyteller view
    )
    trait_data = await sheet_builder.build_sheet_traits()
    inventory = await characters_service(
        user_id=api_user_id,
        campaign_id=character.campaign_id,
    ).list_all_inventory(character_id=character.id)
    notes = await characters_service(
        user_id=api_user_id,
        campaign_id=character.campaign_id,
    ).list_all_notes(character_id=character.id)
    assets = await characters_service(
        user_id=api_user_id,
        campaign_id=character.campaign_id,
    ).list_all_assets(character_id=character.id)

    embeds = []
    embeds.extend(
        [
            await __embed1(
                character,
                player_discord_member=player_discord_member,
                show_footer=show_footer,
                profile_data=profile_data,
                trait_data=trait_data,
                description_prefix=description_prefix,
                description_suffix=description_suffix,
            ),
            await __biography_inventory_embed(
                character,
                player_discord_member=player_discord_member,
                show_footer=show_footer,
                inventory_data=inventory,
            ),
        ],
    )

    if notes:
        embeds.append(
            await __notes_embed(
                character,
                player_discord_member=player_discord_member,
                show_footer=show_footer,
                notes=notes,
            )
        )

    embeds.extend(
        [
            __image_embed(
                character,
                asset=asset,
                player_discord_member=player_discord_member,
                show_footer=show_footer,
            )
            for asset in assets
        ]
    )

    paginator = pages.Paginator(pages=embeds)  # type: ignore [arg-type]
    paginator.remove_button("first")
    paginator.remove_button("last")
    await paginator.respond(ctx.interaction, ephemeral=ephemeral)


async def first_page_of_character_sheet_as_embed(
    ctx: ValentinaContext,
    *,
    character: Character,
    title: str | None = None,
    description_prefix: str | None = None,
    description_suffix: str | None = None,
) -> discord.Embed:
    """Show the first page of a character sheet."""
    sheet_builder = CharacterSheetController(ctx=ctx, character=character)
    player_discord_member = await get_discord_member_from_api_user_id(
        ctx=ctx, api_user_id=character.user_player_id
    )
    concept_dto = (
        await character_blueprint_service().get_concept(concept_id=character.concept_id)
        if character.concept_id
        else None
    )
    profile_data = await sheet_builder.build_profile(
        player_discord_member=player_discord_member, concept_dto=concept_dto
    )
    trait_data = await sheet_builder.build_sheet_traits()

    return await __embed1(
        character,
        player_discord_member=player_discord_member,
        show_footer=False,
        profile_data=profile_data,
        trait_data=trait_data,
        title=title,
        description_prefix=description_prefix,
        description_suffix=description_suffix,
    )
