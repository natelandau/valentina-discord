"""Library functions for the campaign cog."""

from __future__ import annotations

import inflect
from vclient import chapters_service

from vbot.handlers import book_handler, campaign_handler, character_handler
from vbot.utils import truncate_string

p = inflect.engine()


async def build_campaign_list_text(
    user_api_id: str,
    guild_name: str,
) -> str | None:
    """Fetch all campaigns with books, chapters, and characters and format as markdown.

    Args:
        user_api_id: The API user ID for authentication.
        guild_name: The Discord guild name for the header.

    Returns:
        Formatted markdown string, or None if no campaigns exist.
    """
    campaigns = await campaign_handler.list_campaigns(user_api_id=user_api_id)

    if len(campaigns) == 0:
        return None

    text = f"## {len(campaigns)} {p.plural_noun('campaign', len(campaigns))} on `{guild_name}`\n"
    for c in sorted(campaigns, key=lambda x: x.name):
        books = await book_handler.list_books(user_api_id=user_api_id, campaign_api_id=c.id)

        characters = await character_handler.list_characters(
            campaign_api_id=c.id, user_api_id=user_api_id, character_type="PLAYER"
        )

        text += f"### **{c.name}**\n"
        text += f"{truncate_string(c.description, 150)}\n" if c.description else ""

        if len(books) > 0:
            text += f"**{len(books)} {p.plural_noun('book', len(books))}**\n"
            for book in sorted(books, key=lambda x: x.number):
                text += f"- #{book.number}: {book.name}\n"
                chapters = await chapters_service(
                    user_id=user_api_id, campaign_id=c.id, book_id=book.id
                ).list_all()
                for chapter in sorted(chapters, key=lambda x: x.number):
                    text += f"  - Chapter {chapter.number}. {chapter.name}\n"
        text += f"\n**{len(characters)} {p.plural_noun('character', len(characters))}**\n"
        for character in sorted(characters, key=lambda x: x.name):
            text += f"- {character.name}\n"

    return text
