"""Gameplay cog."""

from typing import Annotated

import discord
from discord.commands import Option
from discord.ext import commands
from vclient import character_traits_service, users_service
from vclient.exceptions import NotFoundError
from vclient.models import DicerollCreate

from vbot.bot import Valentina, ValentinaContext
from vbot.cogs import autocompletion
from vbot.constants import DEFAULT_DIFFICULTY
from vbot.handlers import campaign_handler
from vbot.utils.discord import fetch_channel_object
from vbot.views import present_embed

from . import lib


class GameplayCog(commands.Cog):
    """Gameplay cog."""

    def __init__(self, bot: Valentina):
        self.bot = bot

    roll = discord.SlashCommandGroup("roll", "Roll dice")

    @roll.command(description="Throw a roll of d10s")
    async def throw(
        self,
        ctx: ValentinaContext,
        pool: Annotated[int, Option(int, "The number of dice to roll", required=True)],
        difficulty: Annotated[
            int,
            Option(
                int,
                "The difficulty of the roll",
                required=False,
                default=DEFAULT_DIFFICULTY,
            ),
        ],
        desperation: Annotated[
            int,
            Option(
                autocomplete=autocompletion.select_desperation_dice,
                name="desperation",
                description="Add desperation dice",
                required=False,
                default=0,
            ),
        ],
        comment: Annotated[
            str,
            Option(
                str,
                "A comment to display with the roll",
                required=False,
                default=None,
            ),
        ],
    ) -> None:
        """Roll the dice.

        Args:
            comment (str, optional): A comment to display with the roll. Defaults to None.
            ctx (ValentinaContext): The context of the command
            difficulty (int): The difficulty of the roll
            desperation (int): Add x desperation dice to the roll
            pool (int): The number of dice to roll

        """
        user_api_id = await ctx.get_api_user_id()
        channel_objects = await fetch_channel_object(ctx, need_campaign=True)
        db_campaign = channel_objects.campaign
        db_character = channel_objects.character

        campaign_dto = await campaign_handler.get_campaign(
            user_api_id=user_api_id, campaign_api_id=db_campaign.api_id
        )

        diceroll_request = DicerollCreate(
            difficulty=difficulty,
            dice_size=10,
            num_dice=pool,
            num_desperation_dice=desperation,
            comment=comment,
            campaign_id=db_campaign.api_id,
            character_id=db_character.api_id if db_character else None,
        )

        await lib.perform_roll(
            ctx=ctx, diceroll_request=diceroll_request, campaign_dto=campaign_dto
        )

    @roll.command(name="traits", description="Throw a roll based on trait names")
    async def traits(
        self,
        ctx: ValentinaContext,
        trait_api_id_1: Annotated[
            str,
            Option(
                autocomplete=autocompletion.select_character_trait,
                name="trait_one",
                description="First trait to roll",
                required=True,
            ),
        ],
        trait_api_id_2: Annotated[
            str,
            Option(
                autocomplete=autocompletion.select_character_trait,
                name="trait_two",
                description="Second trait to roll",
                required=True,
            ),
        ],
        difficulty: Annotated[
            int,
            Option(
                int,
                "The difficulty of the roll",
                required=False,
                default=DEFAULT_DIFFICULTY,
            ),
        ],
        desperation: Annotated[
            int,
            Option(
                autocomplete=autocompletion.select_desperation_dice,
                name="desperation",
                description="Add desperation dice",
                required=False,
                default=0,
            ),
        ],
        comment: Annotated[
            str,
            Option(
                str,
                "A comment to display with the roll",
                required=False,
                default=None,
            ),
        ],
    ) -> None:
        """Roll the total number of d10s for two given traits against a difficulty."""
        user_api_id = await ctx.get_api_user_id()
        channel_objects = await fetch_channel_object(ctx, need_character=True, need_campaign=True)
        campaign = channel_objects.campaign
        character = channel_objects.character

        campaign_dto = await campaign_handler.get_campaign(
            user_api_id=user_api_id, campaign_api_id=campaign.api_id
        )

        trait_dto_1 = await character_traits_service(
            user_id=user_api_id,
            character_id=character.api_id,
            campaign_id=campaign.api_id,
        ).get(trait_api_id_1)

        trait_ids = [trait_dto_1.id]

        if trait_api_id_2:
            trait_dto_2 = await character_traits_service(
                user_id=user_api_id,
                character_id=character.api_id,
                campaign_id=campaign.api_id,
            ).get(trait_api_id_2)

            trait_ids.append(trait_dto_2.id)

        pool = trait_dto_1.value + trait_dto_2.value if trait_dto_2 else trait_dto_1.value

        diceroll_request = DicerollCreate(
            difficulty=difficulty,
            dice_size=10,
            num_dice=pool,
            num_desperation_dice=desperation,
            comment=comment,
            campaign_id=campaign.api_id,
            character_id=character.api_id,
            trait_ids=trait_ids,
        )

        await lib.perform_roll(
            ctx=ctx,
            diceroll_request=diceroll_request,
            campaign_dto=campaign_dto,
            trait_dtos_for_embed=[trait_dto_1, trait_dto_2],
        )

    @roll.command(name="quickroll", description="Roll a quick roll")
    async def quickroll(
        self,
        ctx: ValentinaContext,
        quick_roll_api_id: Annotated[
            str,
            Option(
                autocomplete=autocompletion.select_quick_roll,
                name="quick_roll",
                description="The quick roll to roll",
                required=True,
            ),
        ],
        difficulty: Annotated[
            int,
            Option(
                int,
                "The difficulty of the roll",
                required=False,
                default=DEFAULT_DIFFICULTY,
            ),
        ],
        desperation: Annotated[
            int,
            Option(
                autocomplete=autocompletion.select_desperation_dice,
                name="desperation",
                description="Add desperation dice",
                required=False,
                default=0,
            ),
        ],
        comment: Annotated[
            str,
            Option(
                str,
                "A comment to display with the roll",
                required=False,
                default=None,
            ),
        ],
        hidden: Annotated[
            bool,
            Option(
                bool,
                "Make the response visible only to you (default true).",
                default=True,
            ),
        ],
    ) -> None:
        """Roll a quick roll."""
        user_api_id = await ctx.get_api_user_id()
        channel_objects = await fetch_channel_object(ctx, need_character=True, need_campaign=True)
        campaign = channel_objects.campaign
        character = channel_objects.character

        campaign_dto = await campaign_handler.get_campaign(
            user_api_id=user_api_id, campaign_api_id=campaign.api_id
        )

        quick_roll_dto = await users_service().get_quickroll(
            user_id=user_api_id, quickroll_id=quick_roll_api_id
        )

        trait_dtos_for_embed = []
        num_dice = 0
        for trait_id in quick_roll_dto.trait_ids:
            try:
                trait_dto = await character_traits_service(
                    user_id=user_api_id,
                    character_id=character.api_id,
                    campaign_id=campaign.api_id,
                ).get(trait_id)
            except NotFoundError:
                await present_embed(
                    ctx,
                    title="This quick roll contains a trait that is not available on this character.",
                    description=f"The trait {trait_id} was not found.",
                    level="error",
                    ephemeral=True,
                )
                return

            num_dice += trait_dto.value
            trait_dtos_for_embed.append(trait_dto)

        diceroll_request = DicerollCreate(
            num_dice=num_dice,
            difficulty=difficulty,
            dice_size=10,
            num_desperation_dice=desperation,
            comment=comment,
            campaign_id=campaign.api_id,
            character_id=character.api_id,
            trait_ids=quick_roll_dto.trait_ids,
        )

        await lib.perform_roll(
            ctx=ctx,
            diceroll_request=diceroll_request,
            campaign_dto=campaign_dto,
            trait_dtos_for_embed=trait_dtos_for_embed,
            quickroll_id=quick_roll_dto.id,
            hidden=hidden,
        )

    @roll.command(description="Simple dice roll of any size.")
    async def dice(
        self,
        ctx: ValentinaContext,
        pool: Annotated[int, Option(int, "The number of dice to roll", required=True)],
        dice_size: Option(  # type: ignore [valid-type]
            int, "Number of sides on the dice.", required=True, choices=[4, 6, 8, 10, 20, 100]
        ),
        comment: Annotated[
            str, Option(str, "A comment to display with the roll", required=False, default=None)
        ],
    ) -> None:
        """Roll any type of dice.

        Args:
            comment (str, optional): A comment to display with the roll. Defaults to None.
            ctx (ValentinaContext): The context of the command
            dice_size (int): The number of sides on the dice
            pool (int): The number of dice to roll
        """
        channel_objects = await fetch_channel_object(ctx, need_campaign=True)
        campaign = channel_objects.campaign
        character = channel_objects.character
        campaign_dto = await campaign_handler.get_campaign(
            user_api_id=await ctx.get_api_user_id(), campaign_api_id=campaign.api_id
        )

        diceroll_request = DicerollCreate(
            difficulty=None,
            dice_size=dice_size,
            num_dice=pool,
            comment=comment,
            campaign_id=campaign.api_id,
            character_id=character.api_id if character else None,
        )

        await lib.perform_roll(
            ctx=ctx, diceroll_request=diceroll_request, campaign_dto=campaign_dto
        )

    @roll.command(name="desperation", description="Roll desperation")
    async def roll_desperation(
        self,
        ctx: ValentinaContext,
        desperation: Annotated[
            int,
            Option(
                autocomplete=autocompletion.select_desperation_dice,
                name="desperation",
                description="Add desperation dice",
                required=True,
            ),
        ],
        difficulty: Annotated[
            int,
            Option(
                int,
                "The difficulty of the roll",
                required=False,
                default=DEFAULT_DIFFICULTY,
            ),
        ],
        comment: Annotated[
            str,
            Option(
                str,
                "A comment to display with the roll",
                required=False,
                default=None,
            ),
        ],
    ) -> None:
        """Roll desperation dice."""
        channel_objects = await fetch_channel_object(ctx, need_campaign=True)
        campaign = channel_objects.campaign
        character = channel_objects.character

        campaign_dto = await campaign_handler.get_campaign(
            user_api_id=await ctx.get_api_user_id(), campaign_api_id=campaign.api_id
        )

        diceroll_request = DicerollCreate(
            difficulty=difficulty,
            dice_size=10,
            num_dice=0,
            num_desperation_dice=desperation,
            comment=comment,
            campaign_id=campaign.api_id,
            character_id=character.api_id if character else None,
        )

        await lib.perform_roll(
            ctx=ctx, diceroll_request=diceroll_request, campaign_dto=campaign_dto
        )


def setup(bot: Valentina) -> None:
    """Register the cog with the bot.

    Initialize and add the cog to the Discord bot's extension system.
    This function is called automatically by the bot's extension loader.

    Args:
        bot (Valentina): The bot instance to register the cog with.
    """
    bot.add_cog(GameplayCog(bot))
