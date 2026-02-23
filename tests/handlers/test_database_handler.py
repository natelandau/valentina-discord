"""Tests for the database handler."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tests.factories import make_campaign, make_campaign_book, make_character, make_user
from vbot.db.models import DBCampaign, DBCampaignBook, DBCharacter, DBUser
from vbot.handlers.database import database_handler

pytestmark = pytest.mark.anyio


class TestUpdateOrCreateCampaign:
    """Tests for DatabaseHandler.update_or_create_campaign()."""

    async def test_creates_new(self, db):
        """Verify creates a new DBCampaign from a Campaign DTO."""
        # Given: a campaign DTO
        campaign = make_campaign(id="camp-001", name="Test Campaign")

        # When: updating or creating in the database
        result = await database_handler.update_or_create_campaign(campaign)

        # Then: a new DB record is created with correct fields
        assert result.api_id == "camp-001"
        assert result.name == "Test Campaign"
        assert await DBCampaign.filter(api_id="camp-001").count() == 1

    async def test_updates_existing(self, db):
        """Verify updates an existing DBCampaign when api_id matches."""
        # Given: an existing campaign in the database
        await DBCampaign.create(api_id="camp-001", name="Old Name")

        # Given: a campaign DTO with the same ID but updated name
        campaign = make_campaign(id="camp-001", name="New Name")

        # When: updating or creating
        result = await database_handler.update_or_create_campaign(campaign)

        # Then: the existing record is updated
        assert result.name == "New Name"
        assert await DBCampaign.filter(api_id="camp-001").count() == 1


class TestUpdateOrCreateBook:
    """Tests for DatabaseHandler.update_or_create_book()."""

    async def test_creates_new(self, db):
        """Verify creates a new DBCampaignBook with campaign FK resolved."""
        # Given: a campaign exists in the database
        await DBCampaign.create(api_id="camp-001", name="Test Campaign")

        # Given: a book DTO linked to that campaign
        book = make_campaign_book(
            id="book-001", name="Chapter One", number=1, campaign_id="camp-001"
        )

        # When: updating or creating
        result = await database_handler.update_or_create_book(book)

        # Then: a new DB record is created with correct FK
        assert result.api_id == "book-001"
        assert result.name == "Chapter One"
        assert result.number == 1
        db_book = await DBCampaignBook.get(api_id="book-001").prefetch_related("campaign")
        assert db_book.campaign.api_id == "camp-001"

    async def test_updates_existing(self, db):
        """Verify updates an existing DBCampaignBook when api_id matches."""
        # Given: a campaign and book exist in the database
        db_campaign = await DBCampaign.create(api_id="camp-001", name="Test Campaign")
        await DBCampaignBook.create(
            api_id="book-001", name="Old Name", number=1, campaign=db_campaign
        )

        # Given: a book DTO with updated name
        book = make_campaign_book(id="book-001", name="New Name", number=2, campaign_id="camp-001")

        # When: updating or creating
        result = await database_handler.update_or_create_book(book)

        # Then: the existing record is updated
        assert result.name == "New Name"
        assert result.number == 2
        assert await DBCampaignBook.filter(api_id="book-001").count() == 1


class TestUpdateOrCreateCharacter:
    """Tests for DatabaseHandler.update_or_create_character()."""

    async def test_creates_new(self, db):
        """Verify creates a new DBCharacter with correct enum mappings."""
        # Given: a campaign exists in the database
        await DBCampaign.create(api_id="camp-001", name="Test Campaign")

        # Given: a character DTO
        character = make_character(
            id="char-001",
            name="John Doe",
            type="PLAYER",
            status="ALIVE",
            campaign_id="camp-001",
            user_player_id="user-001",
            user_creator_id="user-002",
        )

        # When: updating or creating
        result = await database_handler.update_or_create_character(character)

        # Then: a new DB record is created with correct enum values
        assert result.api_id == "char-001"
        assert result.name == "John Doe"
        assert result.type == "PLAYER"
        assert result.status == "ALIVE"
        assert result.user_player_api_id == "user-001"
        assert result.user_creator_api_id == "user-002"

    async def test_updates_existing(self, db):
        """Verify updates an existing DBCharacter when api_id matches."""
        # Given: a campaign and character exist in the database
        db_campaign = await DBCampaign.create(api_id="camp-001", name="Test Campaign")
        await DBCharacter.create(
            api_id="char-001",
            name="Old Name",
            type="PLAYER",
            status="ALIVE",
            campaign=db_campaign,
        )

        # Given: a character DTO with updated name
        character = make_character(
            id="char-001",
            name="New Name",
            type="STORYTELLER",
            status="DEAD",
            campaign_id="camp-001",
        )

        # When: updating or creating
        result = await database_handler.update_or_create_character(character)

        # Then: the existing record is updated with new enum values
        assert result.name == "New Name"
        assert result.type == "STORYTELLER"
        assert result.status == "DEAD"
        assert await DBCharacter.filter(api_id="char-001").count() == 1


class TestUpdateOrCreateUser:
    """Tests for DatabaseHandler.update_or_create_user()."""

    async def test_creates_new(self, db):
        """Verify creates a new DBUser from API User + discord_user."""
        # Given: a user DTO and a discord member mock
        user = make_user(id="user-001", name="Test User", email="test@example.com", role="PLAYER")
        discord_user = MagicMock()
        discord_user.id = 123456789

        # When: updating or creating
        result = await database_handler.update_or_create_user(user, discord_user=discord_user)

        # Then: a new DB record is created with correct fields
        assert result.api_user_id == "user-001"
        assert result.discord_user_id == 123456789
        assert result.name == "Test User"
        assert result.email == "test@example.com"
        assert result.role == "PLAYER"

    async def test_updates_existing(self, db):
        """Verify updates an existing DBUser when discord_user_id matches."""
        # Given: a user exists in the database
        await DBUser.create(
            discord_user_id=123456789,
            api_user_id="user-001",
            name="Old Name",
            role="PLAYER",
        )

        # Given: a user DTO with updated name
        user = make_user(id="user-001", name="New Name", email="new@example.com", role="ADMIN")
        discord_user = MagicMock()
        discord_user.id = 123456789

        # When: updating or creating
        result = await database_handler.update_or_create_user(user, discord_user=discord_user)

        # Then: the existing record is updated
        assert result.name == "New Name"
        assert result.email == "new@example.com"
        assert await DBUser.filter(discord_user_id=123456789).count() == 1


class TestDeleteBook:
    """Tests for DatabaseHandler.delete_book()."""

    async def test_deletes_book(self, db):
        """Verify deletes a book record by api_id."""
        # Given: a campaign and book exist
        db_campaign = await DBCampaign.create(api_id="camp-001", name="Test Campaign")
        await DBCampaignBook.create(api_id="book-001", name="Book", number=1, campaign=db_campaign)

        # When: deleting the book
        await database_handler.delete_book("book-001")

        # Then: the book is removed from the database
        assert await DBCampaignBook.filter(api_id="book-001").count() == 0


class TestDeleteCharacter:
    """Tests for DatabaseHandler.delete_character()."""

    async def test_deletes_character(self, db):
        """Verify deletes a character record by api_id."""
        # Given: a campaign and character exist
        db_campaign = await DBCampaign.create(api_id="camp-001", name="Test Campaign")
        await DBCharacter.create(
            api_id="char-001",
            name="Test Char",
            type="PLAYER",
            status="ALIVE",
            campaign=db_campaign,
        )

        # When: deleting the character
        await database_handler.delete_character("char-001")

        # Then: the character is removed from the database
        assert await DBCharacter.filter(api_id="char-001").count() == 0


class TestDeleteUser:
    """Tests for DatabaseHandler.delete_user()."""

    async def test_deletes_user(self, db):
        """Verify deletes a user record by discord_user_id (int)."""
        # Given: a user exists
        await DBUser.create(
            discord_user_id=123456789,
            api_user_id="user-001",
            name="Test User",
            role="PLAYER",
        )

        # When: deleting the user by discord ID
        await database_handler.delete_user(123456789)

        # Then: the user is removed from the database
        assert await DBUser.filter(discord_user_id=123456789).count() == 0


class TestDeleteCampaign:
    """Tests for DatabaseHandler.delete_campaign()."""

    async def test_deletes_campaign_and_associated_books(self, db):
        """Verify deletes a campaign and its associated books."""
        # Given: a campaign with books exists
        db_campaign = await DBCampaign.create(api_id="camp-001", name="Test Campaign")
        await DBCampaignBook.create(
            api_id="book-001", name="Book 1", number=1, campaign=db_campaign
        )
        await DBCampaignBook.create(
            api_id="book-002", name="Book 2", number=2, campaign=db_campaign
        )

        # When: deleting the campaign
        await database_handler.delete_campaign("camp-001")

        # Then: the campaign and its books are removed
        assert await DBCampaign.filter(api_id="camp-001").count() == 0
        assert await DBCampaignBook.filter(api_id="book-001").count() == 0
        assert await DBCampaignBook.filter(api_id="book-002").count() == 0

    async def test_deletes_campaign_without_books(self, db):
        """Verify deletes a campaign that has no books."""
        # Given: a campaign with no books exists
        await DBCampaign.create(api_id="camp-001", name="Test Campaign")

        # When: deleting the campaign
        await database_handler.delete_campaign("camp-001")

        # Then: the campaign is removed
        assert await DBCampaign.filter(api_id="camp-001").count() == 0

    async def test_deletes_only_target_campaign_books(self, db):
        """Verify deleting a campaign does not affect books of other campaigns."""
        # Given: two campaigns, each with a book
        db_campaign_1 = await DBCampaign.create(api_id="camp-001", name="Campaign 1")
        db_campaign_2 = await DBCampaign.create(api_id="camp-002", name="Campaign 2")
        await DBCampaignBook.create(
            api_id="book-001", name="Book 1", number=1, campaign=db_campaign_1
        )
        await DBCampaignBook.create(
            api_id="book-002", name="Book 2", number=1, campaign=db_campaign_2
        )

        # When: deleting only campaign 1
        await database_handler.delete_campaign("camp-001")

        # Then: campaign 2 and its book are untouched
        assert await DBCampaign.filter(api_id="camp-002").count() == 1
        assert await DBCampaignBook.filter(api_id="book-002").count() == 1
