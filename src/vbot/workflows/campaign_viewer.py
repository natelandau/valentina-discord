"""Campaign viewer workflow for displaying campaign details in Discord."""

import textwrap

import discord
from discord.ext import pages
from vclient import books_service, chapters_service
from vclient.models import Campaign, CampaignBook

from vbot.bot.bot import ValentinaContext
from vbot.constants import ABS_MAX_EMBED_CHARACTERS, EmbedColor, EmojiDict
from vbot.handlers import character_handler
from vbot.utils import num_to_circles

__all__ = ("CampaignViewer",)


class CampaignViewer:
    """Manage and display interactive views of a campaign in a Discord context.

    This class provides an interface for creating and managing different views (pages) of a campaign, such as home, NPCs, and chapters. It utilizes embeds and pagination to present information in an organized and user-friendly manner.

    Attributes:
        ctx (ValentinaContext): The context of the Discord command invoking this viewer.
        campaign (DBCampaign): The campaign object to be displayed.
        max_chars (int): Maximum character limit for text in a single embed.
    """

    def __init__(
        self,
        ctx: ValentinaContext,
        *,
        api_user_id: str,
        campaign: Campaign,
        max_chars: int = ABS_MAX_EMBED_CHARACTERS,
    ) -> None:
        self.ctx: ValentinaContext = ctx
        self.campaign: Campaign = campaign
        self._books: list[CampaignBook] = None

        self.api_user_id: str = api_user_id
        self.max_chars: int = max_chars

    @property
    async def books(self) -> list[CampaignBook]:
        """Get the books for the campaign."""
        if self._books is None:
            self._books = sorted(
                await books_service(
                    user_id=self.api_user_id,  # nosec
                    campaign_id=self.campaign.id,
                ).list_all(),
                key=lambda b: b.number,
            )

        return self._books

    async def _get_pages(self) -> list[pages.PageGroup]:
        """Compile all relevant pages for the campaign view.

        Gather and create page groups for various sections of the campaign like home, NPCs, and chapters, ensuring inclusion of only sections with content.

        Returns:
            list[pages.PageGroup]: A list of PageGroup objects, each representing a different section of the campaign.
        """
        pages = [await self._home_page(), await self._character_page()]

        if len(await self.books) > 0:
            pages.extend(await self._book_pages())

        return pages

    async def _home_page(self) -> pages.PageGroup:
        """Construct the home page view of the campaign.

        Build the home page embed summarizing key campaign information, including description, number of books, and NPCs with proper formatting and styling for presentation.

        Returns:
            pages.PageGroup: A PageGroup object representing the home view of the campaign.
        """
        # TODO: Add campaign statistics
        # TODO: Add campaign NPCs
        # TODO: Add campaign notes
        # TODO: Add book notes

        campaign_description = (
            f"### Description\n{self.campaign.description}" if self.campaign.description else ""
        )

        description_text = f"""\
# {self.campaign.name}
{campaign_description}
### Details
```scala
{EmojiDict.DESPERATION} Desperation : {num_to_circles(self.campaign.desperation)}
{EmojiDict.DANGER} Danger      : {num_to_circles(self.campaign.danger)}
```
```scala
Created  : {self.campaign.date_created.strftime("%Y-%M-%d")}
Modified : {self.campaign.date_modified.strftime("%Y-%M-%d")}
Books    : {len(await self.books)}
```
"""

        home_embed = discord.Embed(
            title="",
            description=description_text,
            color=EmbedColor.DEFAULT.value,
        )
        home_embed.set_author(name="Campaign Overview")
        home_embed.set_footer(text="Navigate Sections with the Dropdown Menu")

        return pages.PageGroup(
            pages=[pages.Page(embeds=[home_embed])],
            label="home",
            description="Campaign Overview",
            use_default_buttons=False,
            emoji="🏠",
        )

    async def _book_pages(self) -> list[pages.PageGroup]:
        """Assemble pages for the campaign's books.

        Create a series of pages, one for each book in the campaign. Present books in individual embeds, using pagination for extensive descriptions.

        Returns:
            list[pages.PageGroup]: A list of PageGroup objects, each signifying a book in the campaign.
        """
        # TODO: Add book notes
        book_pages = []

        for book in await self.books:
            chapters = sorted(
                await chapters_service(
                    user_id=self.api_user_id, campaign_id=self.campaign.id, book_id=book.id
                ).list_all(),
                key=lambda c: c.number,
            )

            book_chapter_list = "### Chapters\n"
            book_chapter_list += "\n".join([f"{c.number}. {c.name}" for c in chapters])

            full_text = ""
            if chapters:
                full_text += f"{book_chapter_list}\n"
            full_text += f"### Description\n{book.description}\n"

            lines = textwrap.wrap(
                full_text,
                self.max_chars,
                break_long_words=False,
                replace_whitespace=False,
            )
            embeds = []
            for line in lines:
                embed = discord.Embed(
                    title="",
                    description=f"## Book #{book.number}: {book.name}\n" + line,
                    color=EmbedColor.DEFAULT.value,
                )
                embeds.append(embed)

            book_page = pages.PageGroup(
                pages=[pages.Page(embeds=[embed]) for embed in embeds],
                label=f"{book.name}",
                description=f"Book #{book.number}",
                custom_buttons=[
                    pages.PaginatorButton("prev", label="←", style=discord.ButtonStyle.green),
                    pages.PaginatorButton(
                        "page_indicator",
                        style=discord.ButtonStyle.gray,
                        disabled=True,
                    ),
                    pages.PaginatorButton("next", label="→", style=discord.ButtonStyle.green),
                ],
                show_disabled=True,
                show_indicator=True,
                loop_pages=False,
                emoji="📖",
            )
            book_pages.append(book_page)

        return book_pages

    async def _character_page(self) -> pages.PageGroup:
        """Construct the character page view of the campaign.

        Build the character page embed summarizing key campaign information, including description, number of books, and NPCs with proper formatting and styling for presentation.

        Returns:
            pages.PageGroup: A PageGroup object representing the character view of the campaign.
        """
        characters = await character_handler.list_characters(
            campaign_api_id=self.campaign.id,
            user_api_id=self.api_user_id,
            character_type="PLAYER",
        )
        character_list = "\n".join(
            [
                f"- **{c.name.title()}** ({c.character_class.title()})"
                for c in sorted(characters, key=lambda x: x.name)
            ]
        )

        return pages.PageGroup(
            pages=[
                pages.Page(
                    embeds=[
                        discord.Embed(
                            title="Characters",
                            description=character_list,
                            color=EmbedColor.DEFAULT.value,
                        )
                    ]
                )
            ],
            label="characters",
            description="Characters",
            use_default_buttons=False,
            emoji="👥",
        )

    async def display(self) -> pages.Paginator:
        """Display the campaign in a Discord paginator.

        Construct a Paginator object that encompasses all pages of the campaign, enabling interactive navigation through the campaign sections in Discord.

        Returns:
            pages.Paginator: A Paginator object for navigating the campaign's views.
        """
        return pages.Paginator(
            pages=await self._get_pages(),
            show_menu=True,
            menu_placeholder="Campaign viewer",
            show_disabled=False,
            show_indicator=False,
            use_default_buttons=False,
            custom_buttons=[],
        )
