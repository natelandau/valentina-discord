"""User cog."""

from typing import Annotated

import discord
from discord.commands import Option
from discord.ext import commands
from vclient import character_blueprint_service, character_traits_service, users_service
from vclient.models import QuickrollCreate

from vbot.bot import Valentina, ValentinaContext
from vbot.cogs import autocompletion
from vbot.constants import EmbedColor
from vbot.handlers import campaign_handler
from vbot.lib.validation import get_valid_linked_db_user
from vbot.utils import experience_to_markdown, statistics_to_markdown
from vbot.utils.discord import fetch_channel_object
from vbot.views import present_embed
from vbot.workflows import confirm_action


class UserCog(commands.Cog):
    """User cog."""

    def __init__(self, bot: Valentina):
        self.bot = bot

    user = discord.SlashCommandGroup("user", "Work with users")
    experience = user.create_subgroup("experience", "Add, spend, or view experience")
    quickroll = user.create_subgroup("quickroll", "Create or delete quick rolls")

    @experience.command(name="add", description="Add experience to a user")
    async def xp_add(
        self,
        ctx: ValentinaContext,
        amount: Annotated[
            int, Option(int, description="The amount of experience to add", required=True)
        ],
        discord_user: Annotated[
            discord.Member,
            Option(
                name="user",
                description="The user to add experience to.",
                required=False,
                default=None,
            ),
        ],
        hidden: Annotated[
            bool,
            Option(
                bool,
                description="Make the response visible only to you (default false).",
                default=False,
                required=False,
            ),
        ],
    ) -> None:
        """Add experience to a user."""
        channel_objects = await fetch_channel_object(ctx, need_campaign=True)
        campaign = channel_objects.campaign

        target_user = await get_valid_linked_db_user(discord_user or ctx.author)

        title = f"Add `{amount}` xp to `{target_user.name}` in `{campaign.name}`"
        is_confirmed, msg, confirmation_embed = await confirm_action(
            ctx=ctx, title=title, hidden=hidden
        )
        if not is_confirmed:
            return

        campaign_experience = await users_service().add_xp(
            user_id=target_user.api_user_id,
            campaign_id=campaign.api_id,
            amount=amount,
            requesting_user_id=await ctx.get_api_user_id(),
        )

        confirmation_embed.title = (
            f"Experience added successfully to `{target_user.name}` in `{campaign.name}`"
        )
        confirmation_embed.description = "### Experience\n" + experience_to_markdown(
            campaign_experience
        )
        await msg.edit_original_response(embed=confirmation_embed, view=None)

    @experience.command(name="add_cool_point", description="Add a cool point to a user")
    async def cp_add(
        self,
        ctx: ValentinaContext,
        discord_user: Annotated[
            discord.Member,
            Option(
                name="user",
                description="The user to add cool points to.",
                required=False,
                default=None,
            ),
        ],
        amount: Annotated[
            int,
            Option(int, description="The amount of cool points to add", required=False, default=1),
        ],
        hidden: Annotated[
            bool,
            Option(
                bool,
                description="Make the response visible only to you (default false).",
                default=False,
            ),
        ],
    ) -> None:
        """Add a cool point to a user."""
        channel_objects = await fetch_channel_object(ctx, need_campaign=True)
        campaign = channel_objects.campaign

        target_user = await get_valid_linked_db_user(discord_user or ctx.author)

        title = f"Add `{amount}` cool point to `{target_user.name}` in `{campaign.name}`"
        is_confirmed, msg, confirmation_embed = await confirm_action(
            ctx=ctx, title=title, hidden=hidden
        )
        if not is_confirmed:
            return

        campaign_experience = await users_service().add_cool_points(
            user_id=target_user.api_user_id,
            campaign_id=campaign.api_id,
            amount=amount,
            requesting_user_id=await ctx.get_api_user_id(),
        )

        confirmation_embed.title = (
            f"Cool point(s) added successfully to `{target_user.name}` in `{campaign.name}`"
        )
        confirmation_embed.description = "### Experience\n" + experience_to_markdown(
            campaign_experience
        )
        await msg.edit_original_response(embed=confirmation_embed, view=None)

    @user.command(name="view", description="View a user")
    async def user_view(
        self,
        ctx: ValentinaContext,
        discord_user: Annotated[
            discord.Member,
            Option(
                name="user", description="The Discord user to view", required=False, default=None
            ),
        ],
    ) -> None:
        """View a user's experience."""
        if not discord_user:
            discord_user = ctx.author  # type: ignore [assignment]

        db_user = await get_valid_linked_db_user(discord_user)
        user_dto = await users_service().get(user_id=db_user.api_user_id)
        user_statistics_dto = await users_service().get_statistics(user_id=db_user.api_user_id)

        embed = discord.Embed(title=f"{user_dto.name}'s profile", color=EmbedColor.INFO.value)
        embed.set_thumbnail(url=discord_user.display_avatar.url)

        embed.add_field(name="Email", value=user_dto.email, inline=True)
        embed.add_field(name="Role", value=user_dto.role, inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        for experience in user_dto.campaign_experience:
            campaign = await campaign_handler.get_campaign(
                user_api_id=await ctx.get_api_user_id(), campaign_api_id=experience.campaign_id
            )
            embed.add_field(
                name=f"**{campaign.name} Experience**",
                value=experience_to_markdown(experience),
                inline=True,
            )

        embed.add_field(
            name="**Roll Statistics**",
            value=statistics_to_markdown(user_statistics_dto, with_help=True),
            inline=False,
        )

        await ctx.respond(embed=embed, ephemeral=True)

    @experience.command(name="spend", description="Spend experience to raise a trait")
    async def xp_spend(
        self,
        ctx: ValentinaContext,
        trait_api_id: Annotated[
            str,
            Option(
                autocomplete=autocompletion.select_character_trait,
                name="trait",
                description="The trait to upgrade.",
                required=True,
            ),
        ],
        amount: Annotated[
            int,
            Option(int, description="Number of dots to add to the trait", required=True),
        ],
        hidden: Annotated[
            bool,
            Option(
                bool,
                description="Make the response visible only to you (default false).",
                default=False,
            ),
        ],
    ) -> None:
        """Spend experience to upgrade a trait."""
        api_user_id = await ctx.get_api_user_id()
        channel_objects = await fetch_channel_object(ctx, need_character=True)
        db_character = channel_objects.character
        await db_character.fetch_related("campaign")

        character_trait_dto = await character_traits_service(
            user_id=api_user_id,
            character_id=db_character.api_id,
            campaign_id=db_character.campaign.api_id,
        ).get(trait_api_id)

        new_value = character_trait_dto.value + amount

        if new_value >= character_trait_dto.trait.max_value:
            await present_embed(
                ctx,
                title=f"Error: {character_trait_dto.trait.name} would exceed max value",
                description=f"Upgrading **{character_trait_dto.trait.name}** by `{amount}` dots would exceed max value of `{character_trait_dto.trait.max_value}`",
                level="error",
                ephemeral=True,
            )
            return

        if api_user_id != db_character.user_player_api_id:
            await present_embed(
                ctx,
                title=f"Error: You are not the owner of {db_character.name}",
                description=f"You are not the owner of {db_character.name} and cannot spend experience on their behalf.",
                level="error",
                ephemeral=True,
            )
            return

        title = f"Upgrade or add {character_trait_dto.trait.name} for {db_character.name}"
        description = f"Cost of upgrade:\n - Initial cost: {character_trait_dto.trait.initial_cost}\n - Upgrade cost per dot: {character_trait_dto.trait.upgrade_cost}"
        is_confirmed, msg, confirmation_embed = await confirm_action(
            ctx=ctx, title=title, description=description, hidden=hidden
        )
        if not is_confirmed:
            return

        updated_character_trait_dto = await character_traits_service(
            user_id=api_user_id,
            character_id=db_character.api_id,
            campaign_id=db_character.campaign.api_id,
        ).change_value(
            character_trait_id=trait_api_id,
            new_value=new_value,
            currency="XP",
        )

        campaign_experience = await users_service().get_experience(
            user_id=api_user_id,
            campaign_id=db_character.campaign.api_id,
        )

        confirmation_embed.title = (
            f"Trait {updated_character_trait_dto.trait.name} upgraded for {db_character.name}"
        )
        confirmation_embed.description = f"**{updated_character_trait_dto.trait.name}** is now at `{updated_character_trait_dto.value}` dots.\nYou have `{campaign_experience.xp_current}` experience points remaining."
        await msg.edit_original_response(embed=confirmation_embed, view=None)

    @experience.command(name="recoup", description="Recoup experience by downgrading a trait")
    async def xp_recoup(
        self,
        ctx: ValentinaContext,
        trait_api_id: Annotated[
            str,
            Option(
                autocomplete=autocompletion.select_character_trait,
                name="trait",
                description="The trait to downgrade.",
                required=True,
            ),
        ],
        amount: Annotated[
            int,
            Option(int, description="Number of dots to downgrade", required=True),
        ],
        hidden: Annotated[
            bool,
            Option(
                bool,
                description="Make the response visible only to you (default false).",
                default=False,
            ),
        ],
    ) -> None:
        """Recoup experience by downgrading a trait."""
        api_user_id = await ctx.get_api_user_id()
        channel_objects = await fetch_channel_object(ctx, need_character=True)
        db_character = channel_objects.character
        await db_character.fetch_related("campaign")

        character_trait_dto = await character_traits_service(
            user_id=api_user_id,
            character_id=db_character.api_id,
            campaign_id=db_character.campaign.api_id,
        ).get(trait_api_id)

        new_value = character_trait_dto.value - amount

        if new_value < character_trait_dto.trait.min_value or new_value < 0:
            await present_embed(
                ctx,
                title=f"Error: {character_trait_dto.trait.name} would exceed min value",
                description=f"Downgrading **{character_trait_dto.trait.name}** by `{amount}` dots would exceed min value of `{character_trait_dto.trait.min_value}`",
                level="error",
                ephemeral=True,
            )
            return

        if api_user_id != db_character.user_player_api_id:
            await present_embed(
                ctx,
                title=f"Error: You are not the owner of {db_character.name}",
                description=f"You are not the owner of {db_character.name} and cannot recoup experience on their behalf.",
                level="error",
                ephemeral=True,
            )
            return

        title = f"Recoup experience by downgrading {character_trait_dto.trait.name} for {db_character.name}"
        is_confirmed, msg, confirmation_embed = await confirm_action(
            ctx=ctx, title=title, hidden=hidden
        )
        if not is_confirmed:
            return

        updated_character_trait_dto = await character_traits_service(
            user_id=api_user_id,
            character_id=db_character.api_id,
            campaign_id=db_character.campaign.api_id,
        ).change_value(
            character_trait_id=trait_api_id,
            new_value=new_value,
            currency="XP",
        )

        campaign_experience = await users_service().get_experience(
            user_id=api_user_id,
            campaign_id=db_character.campaign.api_id,
        )

        confirmation_embed.title = (
            f"Trait {updated_character_trait_dto.trait.name} downgraded for {db_character.name}"
        )
        confirmation_embed.description = f"**{updated_character_trait_dto.trait.name}** is now at `{updated_character_trait_dto.value}` dots.\nYou have `{campaign_experience.xp_current}` experience points remaining."
        await msg.edit_original_response(embed=confirmation_embed, view=None)

    ### Quickroll commands ####################################################################
    @quickroll.command(name="create", description="Create a quick roll")
    async def quickroll_create(
        self,
        ctx: ValentinaContext,
        name: Annotated[str, Option(str, description="The name of the quick roll", required=True)],
        trait_api_id_1: Annotated[
            str,
            Option(
                autocomplete=autocompletion.select_any_trait,
                name="trait_one",
                description="First trait to roll",
                required=True,
            ),
        ],
        trait_api_id_2: Annotated[
            str,
            Option(
                autocomplete=autocompletion.select_any_trait,
                name="trait_two",
                description="Second trait to roll",
                required=True,
            ),
        ],
        quickroll_description: Annotated[
            str,
            Option(
                str,
                description="The description of the quick roll",
                name="description",
                required=False,
                default=None,
            ),
        ],
        hidden: Annotated[
            bool,
            Option(
                bool,
                description="Make the response visible only to you (default true).",
                default=True,
            ),
        ],
    ) -> None:
        """Create a quick roll."""
        api_user_id = await ctx.get_api_user_id()

        trait_1_dto = await character_blueprint_service().get_trait(trait_id=trait_api_id_1)
        trait_2_dto = await character_blueprint_service().get_trait(trait_id=trait_api_id_2)

        title = f"Create quick roll: {name}"
        description = f"{quickroll_description or ''}\n\n - **{trait_1_dto.name}**{':  ' + trait_1_dto.description if trait_1_dto.description else ''}\n - **{trait_2_dto.name}**{':  ' + trait_2_dto.description if trait_2_dto.description else ''}"
        is_confirmed, msg, confirmation_embed = await confirm_action(
            ctx=ctx, title=title, description=description, hidden=hidden
        )
        if not is_confirmed:
            return

        quick_roll_dto = QuickrollCreate(
            name=name,
            trait_ids=[trait_1_dto.id, trait_2_dto.id],
            description=quickroll_description,
        )
        await users_service().create_quickroll(
            user_id=api_user_id,
            request=quick_roll_dto,
        )
        confirmation_embed.title = f"Quick roll created: {name}"
        await msg.edit_original_response(embed=confirmation_embed, view=None)

    @quickroll.command(name="delete", description="Delete a quick roll")
    async def quickroll_delete(
        self,
        ctx: ValentinaContext,
        quick_roll_api_id: Annotated[
            str,
            Option(
                autocomplete=autocompletion.select_quick_roll,
                name="quick_roll",
                description="The quick roll to delete",
                required=True,
            ),
        ],
        hidden: Annotated[
            bool,
            Option(
                bool,
                description="Make the response visible only to you (default true).",
                default=True,
            ),
        ],
    ) -> None:
        """Delete a quick roll."""
        if not quick_roll_api_id:
            await present_embed(
                ctx,
                title="Error: No quick roll selected",
                description="Please select a quick roll to delete.",
                level="error",
                ephemeral=True,
            )
            return

        api_user_id = await ctx.get_api_user_id()
        quick_roll_dto = await users_service().get_quickroll(
            user_id=api_user_id,
            quickroll_id=quick_roll_api_id,
        )

        title = f"Delete quick roll: {quick_roll_dto.name}"
        description = f"Are you sure you want to delete the quick roll {quick_roll_dto.name}?\n\nThis is a destructive action."
        is_confirmed, msg, confirmation_embed = await confirm_action(
            ctx=ctx, title=title, description=description, hidden=hidden
        )
        if not is_confirmed:
            return

        await users_service().delete_quickroll(
            user_id=api_user_id,
            quickroll_id=quick_roll_api_id,
        )
        confirmation_embed.title = f"Quick roll deleted: {quick_roll_dto.name}"
        await msg.edit_original_response(embed=confirmation_embed, view=None)

    @quickroll.command(name="list", description="List your quick rolls")
    async def quickroll_list(self, ctx: ValentinaContext) -> None:
        """List your quick rolls."""
        api_user_id = await ctx.get_api_user_id()
        quick_rolls = await users_service().list_all_quickrolls(user_id=api_user_id)
        if not quick_rolls:
            await present_embed(
                ctx,
                title="No quick rolls found",
                description="You have no quick rolls.",
                level="info",
                ephemeral=True,
            )
            return

        title = "Quick rolls"
        description = ""
        for i, quick_roll in enumerate(sorted(quick_rolls, key=lambda x: x.name)):
            trait_descriptions = []
            for trait_id in quick_roll.trait_ids:
                trait_dto = await character_blueprint_service().get_trait(trait_id=trait_id)
                trait_descriptions.append(
                    f"- **{trait_dto.name.title()}**{':  ' + trait_dto.description if trait_dto.description else ''}"
                )

            description += f"### {i + 1}. {quick_roll.name.title()}\n{quick_roll.description + '\n' if quick_roll.description else ''}\n{'\n'.join(trait_descriptions)}\n"

        await present_embed(ctx, title=title, description=description, level="info", ephemeral=True)


def setup(bot: Valentina) -> None:
    """Register the cog with the bot.

    Initialize and add the cog to the Discord bot's extension system.
    This function is called automatically by the bot's extension loader.

    Args:
        bot (Valentina): The bot instance to register the cog with.
    """
    bot.add_cog(UserCog(bot))
