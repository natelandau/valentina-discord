"""Library for the gameplay cog."""

import discord
from vclient import dicerolls_service
from vclient.models import Campaign, CharacterTrait, DicerollCreate

from vbot.bot import ValentinaContext
from vbot.constants import EmbedColor, EmojiDict
from vbot.views import present_embed
from vbot.workflows import ReRollButton, RollDisplay


async def perform_roll(
    *,
    ctx: ValentinaContext,
    diceroll_request: DicerollCreate,
    campaign_dto: Campaign,
    trait_dtos_for_embed: list[CharacterTrait] = [],
    quickroll_id: str | None = None,
    hidden: bool = False,
) -> None:
    """Perform a roll."""
    user_api_id = await ctx.get_api_user_id()
    if diceroll_request.num_desperation_dice > 0 and campaign_dto.desperation == 0:
        await present_embed(
            ctx,
            title="Can not roll desperation",
            description=f"Current desperation level is `0` and you tried to roll `{diceroll_request.num_desperation_dice} desperation` dice.",
            level="error",
            ephemeral=True,
        )
        return

    if quickroll_id:
        diceroll = await dicerolls_service(user_id=user_api_id).create_from_quickroll(
            quickroll_id=quickroll_id,
            comment=diceroll_request.comment,
            character_id=diceroll_request.character_id,
            difficulty=diceroll_request.difficulty,
            num_desperation_dice=diceroll_request.num_desperation_dice,
        )
    else:
        diceroll = await dicerolls_service(user_id=user_api_id).create(request=diceroll_request)

    view = ReRollButton(author=ctx.author, diceroll=diceroll)
    embed = await RollDisplay(
        ctx, diceroll=diceroll, trait_dtos_for_embed=trait_dtos_for_embed
    ).get_embed()
    original_response = await ctx.respond(embed=embed, view=view, ephemeral=hidden)

    # Wait for a re-roll
    await view.wait()

    if view.overreach:
        if campaign_dto.danger < 5:  # noqa: PLR2004
            campaign_dto.danger += 1
            # TODO: Post the updated danger level to the api

        await original_response.edit_original_response(  # type: ignore [union-attr]
            view=None,
            embed=discord.Embed(
                title=None,
                description=f"# {EmojiDict.OVERREACH} Overreach!\nThe character overreached. This roll has succeeded but the danger level has increased to `{campaign_dto.danger}`.",
                color=EmbedColor.WARNING.value,
            ),
        )

    if view.despair:
        await original_response.edit_original_response(  # type: ignore [union-attr]
            view=None,
            embed=discord.Embed(
                title=None,
                description=f"# {EmojiDict.DESPAIR} Despair!\n### This roll has failed and the character has entered Despair!\nYou can no longer use desperation dice until you redeem yourself.",
                color=EmbedColor.WARNING.value,
            ),
        )

    if view.timeout:
        if isinstance(original_response, discord.Interaction):
            await original_response.edit_original_response(view=None)
        if isinstance(original_response, discord.WebhookMessage):
            await original_response.edit(view=None)

    if view.reroll:
        await perform_roll(
            ctx=ctx,
            diceroll_request=diceroll_request,
            campaign_dto=campaign_dto,
            hidden=hidden,
            trait_dtos_for_embed=trait_dtos_for_embed,
            quickroll_id=quickroll_id,
        )
