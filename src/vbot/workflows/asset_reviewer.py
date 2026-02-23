"""Asset reviewer workflow."""

import discord
from discord.ext import pages
from discord.ui import Button
from vclient.models import Asset

from vbot.bot import ValentinaContext
from vbot.constants import EmbedColor, EmojiDict
from vbot.handlers import delete_asset_handler


class DeleteAssetButtons(discord.ui.View):
    """A view for deleting assets."""

    def __init__(self, ctx: ValentinaContext, asset: Asset) -> None:
        super().__init__()
        self.ctx = ctx
        self.asset = asset

    @discord.ui.button(
        label=f"{EmojiDict.WARNING} Delete asset",
        style=discord.ButtonStyle.danger,
        custom_id="delete",
        row=1,
    )
    async def confirm_callback(self, button: Button, interaction: discord.Interaction) -> None:
        """Callback for the confirm button."""
        button.label = f"{EmojiDict.SUCCESS} Asset deleted"
        button.style = discord.ButtonStyle.secondary
        self.disable_all_items()

        user_api_id = await self.ctx.get_api_user_id()
        await delete_asset_handler(self.asset, user_api_id=user_api_id)

        # Respond to user
        await interaction.response.edit_message(
            embed=discord.Embed(
                title=f"Delete image `{self.asset.original_filename}`",
                color=EmbedColor.SUCCESS.value,
            ),
            view=None,
        )  # view=None removes all buttons
        self.stop()

    @discord.ui.button(
        label=f"{EmojiDict.YES} Complete Review",
        style=discord.ButtonStyle.primary,
        custom_id="done",
        row=1,
    )
    async def done_callback(
        self,
        button: Button,  # noqa: ARG002
        interaction: discord.Interaction,
    ) -> None:
        """Callback for the re-roll button."""
        await interaction.response.edit_message(
            embed=discord.Embed(title="Done reviewing images", color=EmbedColor.INFO.value),
            view=None,
        )  # view=None remove all buttons
        self.stop()


class AssetReviewHandler:
    """Paginated view for reviewing assets."""

    def __init__(self, ctx: ValentinaContext, *, assets: list[Asset], hidden: bool = False):
        self.ctx = ctx
        self.assets = assets
        self.hidden = hidden

    async def _build_pages(self) -> list[pages.Page]:
        """Build the pages for the paginator. Create an embed for each asset and add it to a single page paginator with a custom view allowing it to be deleted/categorized.  Then return a list of all the paginators."""
        pages_to_send: list[pages.Page] = []

        for asset in self.assets:
            view = DeleteAssetButtons(ctx=self.ctx, asset=asset)

            embed = discord.Embed(title=asset.original_filename, color=EmbedColor.DEFAULT.value)
            embed.set_image(url=asset.public_url)
            pages_to_send.append(
                pages.Page(
                    embeds=[embed],
                    label=f"Asset: {asset.original_filename}",
                    description="Use the buttons below to delete this image",
                    use_default_buttons=False,
                    custom_view=view,
                ),
            )

        return pages_to_send

    async def send(self) -> None:
        """Send the paginator."""
        if not self.assets:
            await self.ctx.respond(
                embed=discord.Embed(
                    title="No assets to review",
                    color=EmbedColor.INFO.value,
                ),
                ephemeral=self.hidden,
            )
            return

        paginators = await self._build_pages()

        paginator = pages.Paginator(pages=paginators, show_menu=False, disable_on_timeout=True)
        paginator.remove_button("first")
        paginator.remove_button("last")
        await paginator.respond(self.ctx.interaction, ephemeral=self.hidden)
