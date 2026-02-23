"""Tests for Tortoise ORM model custom methods."""

from __future__ import annotations

import pytest

from vbot.constants import EmojiDict
from vbot.db.models import DBCampaign, DBCampaignBook, DBCharacter, DBUser

pytestmark = pytest.mark.anyio


# ---------------------------------------------------------------------------
# DBCharacter.get_channel_name() — uses Model.construct(), no DB needed
# ---------------------------------------------------------------------------


class TestDBCharacterGetChannelName:
    """Tests for DBCharacter.get_channel_name()."""

    def test_player_alive(self):
        """Verify alive player character channel name uses player emoji."""
        character = DBCharacter.construct(
            name="John Doe",
            type="PLAYER",
            status="ALIVE",
        )
        assert character.get_channel_name() == f"{EmojiDict.CHANNEL_PLAYER}-john-doe"

    def test_player_dead(self):
        """Verify dead player character channel name uses dead emoji."""
        character = DBCharacter.construct(
            name="John Doe",
            type="PLAYER",
            status="DEAD",
        )
        assert character.get_channel_name() == f"{EmojiDict.CHANNEL_PLAYER_DEAD}-john-doe"

    def test_storyteller_alive(self):
        """Verify alive storyteller channel name includes private prefix."""
        character = DBCharacter.construct(
            name="Jane Smith",
            type="STORYTELLER",
            status="ALIVE",
        )
        expected = f"{EmojiDict.CHANNEL_PRIVATE}{EmojiDict.CHANNEL_PLAYER}-jane-smith"
        assert character.get_channel_name() == expected

    def test_storyteller_dead(self):
        """Verify dead storyteller channel name uses dead emoji with private prefix."""
        character = DBCharacter.construct(
            name="Jane Smith",
            type="STORYTELLER",
            status="DEAD",
        )
        expected = f"{EmojiDict.CHANNEL_PRIVATE}{EmojiDict.CHANNEL_PLAYER_DEAD}-jane-smith"
        assert character.get_channel_name() == expected


# ---------------------------------------------------------------------------
# DBCharacter.get_user_player_discord_id() — needs DB fixture
# ---------------------------------------------------------------------------


class TestDBCharacterGetUserPlayerDiscordId:
    """Tests for DBCharacter.get_user_player_discord_id()."""

    async def test_found(self, db):
        """Verify returns Discord ID when user exists in DB."""
        # Given: a user and campaign exist in the DB
        await DBUser.create(
            discord_user_id=123456789,
            api_user_id="user-001",
            name="Test User",
            role="PLAYER",
        )
        campaign = await DBCampaign.create(api_id="campaign-001", name="Test Campaign")

        # Given: a character linked to the user
        character = await DBCharacter.create(
            api_id="char-001",
            name="Test Char",
            type="PLAYER",
            status="ALIVE",
            user_player_api_id="user-001",
            campaign=campaign,
        )

        # When: resolving the player's discord ID
        result = await character.get_user_player_discord_id()

        # Then: the correct discord ID is returned
        assert result == 123456789

    async def test_not_found(self, db):
        """Verify returns None when no matching user in DB."""
        # Given: a character with a player API ID that has no matching DBUser
        campaign = await DBCampaign.create(api_id="campaign-001", name="Test Campaign")
        character = await DBCharacter.create(
            api_id="char-001",
            name="Test Char",
            type="PLAYER",
            status="ALIVE",
            user_player_api_id="nonexistent-user",
            campaign=campaign,
        )

        # When/Then
        result = await character.get_user_player_discord_id()
        assert result is None

    async def test_no_player(self, db):
        """Verify returns None when user_player_api_id is None."""
        # Given: a character with no player assigned
        campaign = await DBCampaign.create(api_id="campaign-001", name="Test Campaign")
        character = await DBCharacter.create(
            api_id="char-001",
            name="Test Char",
            type="NPC",
            status="ALIVE",
            user_player_api_id=None,
            campaign=campaign,
        )

        # When/Then
        result = await character.get_user_player_discord_id()
        assert result is None


# ---------------------------------------------------------------------------
# DBCampaignBook.get_channel_name() — uses Model.construct(), no DB needed
# ---------------------------------------------------------------------------


def test_book_get_channel_name():
    """Verify book channel name includes emoji, zero-padded number, and lowercase name."""
    book = DBCampaignBook.construct(name="The Awakening", number=3)
    assert book.get_channel_name() == f"{EmojiDict.BOOK}-03-the-awakening"


# ---------------------------------------------------------------------------
# DBCampaign.get_category_channel_name() — uses Model.construct(), no DB needed
# ---------------------------------------------------------------------------


def test_campaign_get_category_channel_name():
    """Verify campaign category channel name includes books emoji and lowercase name."""
    campaign = DBCampaign.construct(name="Blood Moon Rising")
    assert campaign.get_category_channel_name() == f"{EmojiDict.BOOKS}-blood-moon-rising"
