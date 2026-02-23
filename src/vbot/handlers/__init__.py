"""Handlers for the bot."""

from .assets import delete_asset_handler
from .book import book_handler
from .campaign import campaign_handler
from .character import character_handler
from .database import database_handler
from .user import user_api_handler

__all__ = (
    "book_handler",
    "campaign_handler",
    "character_handler",
    "database_handler",
    "delete_asset_handler",
    "user_api_handler",
)
