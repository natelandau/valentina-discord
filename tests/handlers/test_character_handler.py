"""Tests for the character API handler."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tests.factories import make_character
from vbot.db.models import DBCampaign, DBCharacter
from vbot.handlers.character import character_handler

pytestmark = pytest.mark.anyio


class TestListCharacters:
    """Tests for CharacterAPIHandler.list_characters()."""

    async def test_returns_characters(self, db, mock_characters_service):
        """Verify delegates to API with filtering params passed as strings."""
        # Given: a campaign exists in the DB
        await DBCampaign.create(api_id="camp-001", name="Test Campaign")

        # Given: the API returns characters
        characters = [
            make_character(id="char-001", name="Alice"),
            make_character(id="char-002", name="Bob"),
        ]
        mock_characters_service._service.list_all.return_value = characters

        # When: listing characters with filter params
        result = await character_handler.list_characters(
            campaign_api_id="camp-001",
            user_api_id="user-001",
            character_class="VAMPIRE",
            character_type="PLAYER",
            status="ALIVE",
        )

        # Then: API was called with string values
        mock_characters_service.assert_called_once_with(user_id="user-001", campaign_id="camp-001")
        call_kwargs = mock_characters_service._service.list_all.call_args[1]
        assert call_kwargs["character_class"] == "VAMPIRE"
        assert call_kwargs["character_type"] == "PLAYER"
        assert call_kwargs["status"] == "ALIVE"

        # Then: results returned and synced to DB
        assert len(result) == 2
        assert await DBCharacter.filter(api_id="char-001").count() == 1
        assert await DBCharacter.filter(api_id="char-002").count() == 1

    async def test_none_filters_passed_as_none(self, db, mock_characters_service):
        """Verify None filter params are passed as None to the API."""
        # Given: a campaign exists
        await DBCampaign.create(api_id="camp-001", name="Test Campaign")
        mock_characters_service._service.list_all.return_value = []

        # When: listing with no filters
        await character_handler.list_characters(
            campaign_api_id="camp-001",
            user_api_id="user-001",
        )

        # Then: all filter params are None
        call_kwargs = mock_characters_service._service.list_all.call_args[1]
        assert call_kwargs["character_class"] is None
        assert call_kwargs["character_type"] is None
        assert call_kwargs["status"] is None


class TestGetCharacter:
    """Tests for CharacterAPIHandler.get_character()."""

    async def test_returns_character(self, db, mock_characters_service):
        """Verify delegates to API and syncs to DB."""
        # Given: a campaign exists
        await DBCampaign.create(api_id="camp-001", name="Test Campaign")

        # Given: the API returns a character
        character = make_character(id="char-001", name="Test Char")
        mock_characters_service._service.get.return_value = character

        # When: getting a character
        result = await character_handler.get_character(
            user_api_id="user-001", campaign_api_id="camp-001", character_api_id="char-001"
        )

        # Then: API was called correctly
        mock_characters_service._service.get.assert_awaited_once_with("char-001")
        assert result.name == "Test Char"

        # Then: character is synced to DB
        assert await DBCharacter.filter(api_id="char-001").count() == 1


class TestUpdateOrCreateCharacterInDb:
    """Tests for CharacterAPIHandler.update_or_create_character_in_db()."""

    async def test_correct_db_fields(self, db):
        """Verify correct DB fields mapped including enum conversions and campaign FK."""
        # Given: a campaign exists
        await DBCampaign.create(api_id="camp-001", name="Test Campaign")

        # Given: a character DTO
        character = make_character(
            id="char-001",
            name="John Doe",
            type="STORYTELLER",
            status="DEAD",
            campaign_id="camp-001",
            user_player_id="user-p1",
            user_creator_id="user-c1",
        )

        # When: syncing to DB
        db_char = await character_handler.update_or_create_character_in_db(character)

        # Then: string values are stored directly
        assert db_char.type == "STORYTELLER"
        assert db_char.status == "DEAD"
        assert db_char.user_player_api_id == "user-p1"
        assert db_char.user_creator_api_id == "user-c1"

        # Then: campaign FK is resolved
        db_char_full = await DBCharacter.get(api_id="char-001").prefetch_related("campaign")
        assert db_char_full.campaign.api_id == "camp-001"


class TestCreateCharacter:
    """Tests for CharacterAPIHandler.create_character()."""

    async def test_creates_character(self, db, mock_characters_service, mock_valentina_context):
        """Verify CharacterCreate DTO built, API called, and DB synced."""
        # Given: a campaign exists
        await DBCampaign.create(api_id="camp-001", name="Test Campaign")

        # Given: the API returns a created character
        character = make_character(id="char-001", name="Jane Doe")
        mock_characters_service._service.create.return_value = character

        # When: creating a character
        result = await character_handler.create_character(
            mock_valentina_context,
            campaign_api_id="camp-001",
            character_class="VAMPIRE",
            game_version="V5",
            name_first="Jane",
            name_last="Doe",
        )

        # Then: ctx.get_api_user_id() was called
        mock_valentina_context.get_api_user_id.assert_awaited_once()

        # Then: API was called with a CharacterCreate request
        mock_characters_service._service.create.assert_awaited_once()
        call_kwargs = mock_characters_service._service.create.call_args[1]
        request = call_kwargs["request"]
        assert request.name_first == "Jane"
        assert request.name_last == "Doe"
        assert request.character_class == "VAMPIRE"
        assert request.game_version == "V5"

        # Then: character is synced to DB
        assert await DBCharacter.filter(api_id="char-001").count() == 1
        assert result.name == "Jane Doe"


class TestUpdateCharacter:
    """Tests for CharacterAPIHandler.update_character()."""

    async def test_delegates_to_api_and_syncs_db(
        self, db, mock_characters_service, mock_valentina_context
    ):
        """Verify API update called with all params and result synced to DB."""
        # Given: a campaign exists
        await DBCampaign.create(api_id="camp-001", name="Test Campaign")

        # Given: the API returns an updated character
        character = make_character(id="char-001", name="Updated Name")
        mock_characters_service._service.update.return_value = character

        # When: updating a character with basic fields
        result = await character_handler.update_character(
            mock_valentina_context,
            campaign_api_id="camp-001",
            character_api_id="char-001",
            age=30,
            biography="A dark past",
        )

        # Then: ctx.get_api_user_id() was called
        mock_valentina_context.get_api_user_id.assert_awaited_once()

        # Then: API was called with correct service params
        mock_characters_service.assert_called_once_with(user_id="user-001", campaign_id="camp-001")

        # Then: API update was called with character ID and kwargs
        call_kwargs = mock_characters_service._service.update.call_args
        assert call_kwargs[0][0] == "char-001"
        assert call_kwargs[1]["age"] == 30
        assert call_kwargs[1]["biography"] == "A dark past"

        # Then: result returned and synced to DB
        assert result.name == "Updated Name"
        assert await DBCharacter.filter(api_id="char-001").count() == 1

    async def test_none_params_passed_as_none(
        self, db, mock_characters_service, mock_valentina_context
    ):
        """Verify omitted params are passed as None to the API."""
        # Given: a campaign exists
        await DBCampaign.create(api_id="camp-001", name="Test Campaign")
        character = make_character(id="char-001")
        mock_characters_service._service.update.return_value = character

        # When: updating with no optional fields
        await character_handler.update_character(
            mock_valentina_context,
            campaign_api_id="camp-001",
            character_api_id="char-001",
        )

        # Then: all optional params are None
        call_kwargs = mock_characters_service._service.update.call_args[1]
        assert call_kwargs["character_class"] is None
        assert call_kwargs["character_type"] is None
        assert call_kwargs["game_version"] is None
        assert call_kwargs["status"] is None
        assert call_kwargs["name_first"] is None
        assert call_kwargs["name_last"] is None
        assert call_kwargs["name_nick"] is None
        assert call_kwargs["age"] is None

    @pytest.mark.parametrize(
        "trigger_field",
        [
            {"name_first": "Alice"},
            {"name_last": "Smith"},
            {"name_nick": "Ace"},
            {"status": "DEAD"},
            {"character_type": "STORYTELLER"},
        ],
        ids=["name_first", "name_last", "name_nick", "status", "character_type"],
    )
    async def test_channel_refresh_on_trigger_fields(
        self, db, mock_characters_service, mock_valentina_context, mocker, trigger_field
    ):
        """Verify channel manager called when name, status, or type changes."""
        # Given: a campaign exists
        await DBCampaign.create(api_id="camp-001", name="Test Campaign")
        character = make_character(id="char-001")
        mock_characters_service._service.update.return_value = character

        # Given: ChannelManager is mocked at the handler's import location
        mock_cm_cls = mocker.patch("vbot.handlers.character.ChannelManager", autospec=True)
        mock_cm_instance = AsyncMock()
        mock_cm_cls.return_value = mock_cm_instance

        # When: updating with a trigger field
        await character_handler.update_character(
            mock_valentina_context,
            campaign_api_id="camp-001",
            character_api_id="char-001",
            **trigger_field,
        )

        # Then: ChannelManager was created with the guild
        mock_cm_cls.assert_called_once_with(guild=mock_valentina_context.guild)

        # Then: channel operations were performed
        mock_cm_instance.confirm_character_channel.assert_awaited_once()
        mock_cm_instance.sort_campaign_channels.assert_awaited_once()

    async def test_no_channel_refresh_without_trigger_fields(
        self, db, mock_characters_service, mock_valentina_context, mocker
    ):
        """Verify channel manager not called when only non-trigger fields change."""
        # Given: a campaign exists
        await DBCampaign.create(api_id="camp-001", name="Test Campaign")
        character = make_character(id="char-001")
        mock_characters_service._service.update.return_value = character

        # Given: ChannelManager is mocked
        mock_cm_cls = mocker.patch("vbot.handlers.character.ChannelManager", autospec=True)

        # When: updating with only non-trigger fields
        await character_handler.update_character(
            mock_valentina_context,
            campaign_api_id="camp-001",
            character_api_id="char-001",
            age=25,
            biography="Just a biography update",
        )

        # Then: ChannelManager was never instantiated
        mock_cm_cls.assert_not_called()

    async def test_no_channel_refresh_when_campaign_not_in_db(
        self, db, mock_characters_service, mock_valentina_context, mocker
    ):
        """Verify channel manager skipped when campaign has no DB record."""
        # Given: the campaign does NOT exist in DB (API-only)
        # But we still need a campaign for update_or_create_character_in_db
        # The character factory defaults to campaign_id="campaign-001"
        character = make_character(id="char-001", campaign_id="camp-missing")
        mock_characters_service._service.update.return_value = character

        # Given: ChannelManager is mocked
        mock_cm_cls = mocker.patch("vbot.handlers.character.ChannelManager", autospec=True)

        # When: updating with a trigger field but campaign not in DB
        await character_handler.update_character(
            mock_valentina_context,
            campaign_api_id="camp-missing",
            character_api_id="char-001",
            name_first="Alice",
        )

        # Then: ChannelManager was never instantiated
        mock_cm_cls.assert_not_called()


class TestDeleteCharacter:
    """Tests for CharacterAPIHandler.delete_character()."""

    async def test_deletes_character_and_channel(
        self, db, mock_characters_service, mock_valentina_context, mocker
    ):
        """Verify API delete called, channel deleted, and DB record removed."""
        # Given: a campaign and character exist in DB
        db_campaign = await DBCampaign.create(api_id="camp-001", name="Test Campaign")
        await DBCharacter.create(
            api_id="char-001",
            name="Doomed Char",
            type="PLAYER",
            status="ALIVE",
            campaign=db_campaign,
        )

        # Given: ChannelManager is mocked
        mock_cm_cls = mocker.patch("vbot.handlers.character.ChannelManager", autospec=True)
        mock_cm_instance = AsyncMock()
        mock_cm_cls.return_value = mock_cm_instance

        # When: deleting the character
        await character_handler.delete_character(
            mock_valentina_context,
            user_api_id="user-001",
            campaign_api_id="camp-001",
            character_api_id="char-001",
        )

        # Then: API delete was called
        mock_characters_service._service.delete.assert_awaited_once_with("char-001")

        # Then: channel was deleted
        mock_cm_cls.assert_called_once_with(guild=mock_valentina_context.guild)
        mock_cm_instance.delete_character_channel.assert_awaited_once()

        # Then: DB record is removed
        assert await DBCharacter.filter(api_id="char-001").count() == 0

    async def test_no_channel_delete_when_character_not_in_db(
        self, db, mock_characters_service, mock_valentina_context, mocker
    ):
        """Verify channel manager skipped when character has no DB record."""
        # Given: ChannelManager is mocked
        mock_cm_cls = mocker.patch("vbot.handlers.character.ChannelManager", autospec=True)

        # When: deleting a character that only exists in the API (not in DB)
        await character_handler.delete_character(
            mock_valentina_context,
            user_api_id="user-001",
            campaign_api_id="camp-001",
            character_api_id="char-999",
        )

        # Then: API delete was still called
        mock_characters_service._service.delete.assert_awaited_once_with("char-999")

        # Then: ChannelManager was never instantiated
        mock_cm_cls.assert_not_called()
