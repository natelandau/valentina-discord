"""Tests for the character API handler."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from vclient.endpoints import Endpoints
from vclient.testing import CharacterFactory

from vbot.db.models import DBCampaign, DBCharacter
from vbot.handlers.character import character_handler

pytestmark = pytest.mark.anyio


def _character_list_response(*characters) -> dict:
    """Build a paginated list response from character instances."""
    return {
        "items": [c.model_dump(mode="json") for c in characters],
        "total": len(characters),
        "limit": 100,
        "offset": 0,
    }


class TestListCharacters:
    """Tests for CharacterAPIHandler.list_characters()."""

    async def test_returns_characters(self, db, fake_vclient):
        """Verify delegates to API with filtering params and syncs to DB."""
        # Given: a campaign exists in the DB
        await DBCampaign.create(api_id="camp-001", name="Test Campaign")

        # Given: the API returns characters
        c1 = CharacterFactory.build(id="char-001", name="Alice", campaign_id="camp-001")
        c2 = CharacterFactory.build(id="char-002", name="Bob", campaign_id="camp-001")
        fake_vclient.add_route("GET", Endpoints.CHARACTERS, json=_character_list_response(c1, c2))

        # When: listing characters with filter params
        result = await character_handler.list_characters(
            campaign_api_id="camp-001",
            user_api_id="user-001",
            character_class="VAMPIRE",
            character_type="PLAYER",
            status="ALIVE",
        )

        # Then: results returned and synced to DB
        assert len(result) == 2
        assert await DBCharacter.filter(api_id="char-001").count() == 1
        assert await DBCharacter.filter(api_id="char-002").count() == 1

    async def test_none_filters(self, db, fake_vclient):
        """Verify handler works with no filter params."""
        # Given: a campaign exists
        await DBCampaign.create(api_id="camp-001", name="Test Campaign")
        fake_vclient.add_route("GET", Endpoints.CHARACTERS, json=_character_list_response())

        # When: listing with no filters
        result = await character_handler.list_characters(
            campaign_api_id="camp-001",
            user_api_id="user-001",
        )

        # Then: empty list returned without error
        assert result == []


class TestGetCharacter:
    """Tests for CharacterAPIHandler.get_character()."""

    async def test_returns_character(self, db, fake_vclient):
        """Verify delegates to API and syncs to DB."""
        # Given: a campaign exists
        await DBCampaign.create(api_id="camp-001", name="Test Campaign")

        # Given: the API returns a character
        character = CharacterFactory.build(id="char-001", name="Test Char", campaign_id="camp-001")
        fake_vclient.add_route("GET", Endpoints.CHARACTER, json=character.model_dump(mode="json"))

        # When: getting a character
        result = await character_handler.get_character(
            user_api_id="user-001", campaign_api_id="camp-001", character_api_id="char-001"
        )

        # Then: correct character returned and synced to DB
        assert result.name == "Test Char"
        assert await DBCharacter.filter(api_id="char-001").count() == 1


class TestUpdateOrCreateCharacterInDb:
    """Tests for CharacterAPIHandler.update_or_create_character_in_db()."""

    async def test_correct_db_fields(self, db):
        """Verify correct DB fields mapped including enum conversions and campaign FK."""
        # Given: a campaign exists
        await DBCampaign.create(api_id="camp-001", name="Test Campaign")

        # Given: a character DTO
        character = CharacterFactory.build(
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

    async def test_creates_character(self, db, fake_vclient, mock_valentina_context):
        """Verify CharacterCreate DTO built, API called, and DB synced."""
        # Given: a campaign exists
        await DBCampaign.create(api_id="camp-001", name="Test Campaign")

        # Given: the API returns a created character
        character = CharacterFactory.build(id="char-001", name="Jane Doe", campaign_id="camp-001")
        fake_vclient.add_route(
            "POST",
            Endpoints.CHARACTERS,
            json=character.model_dump(mode="json"),
            status_code=201,
        )

        # When: creating a character
        result = await character_handler.create_character(
            mock_valentina_context,
            campaign_api_id="camp-001",
            character_class="VAMPIRE",
            game_version="V5",
            name_first="Jane",
            name_last="Doe",
        )

        # Then: character is synced to DB
        assert await DBCharacter.filter(api_id="char-001").count() == 1
        assert result.name == "Jane Doe"


class TestUpdateCharacter:
    """Tests for CharacterAPIHandler.update_character()."""

    async def test_delegates_to_api_and_syncs_db(self, db, fake_vclient, mock_valentina_context):
        """Verify API update called and result synced to DB."""
        # Given: a campaign exists
        await DBCampaign.create(api_id="camp-001", name="Test Campaign")

        # Given: the API returns an updated character
        character = CharacterFactory.build(
            id="char-001", name="Updated Name", campaign_id="camp-001"
        )
        fake_vclient.add_route("PATCH", Endpoints.CHARACTER, json=character.model_dump(mode="json"))

        # When: updating a character with basic fields
        result = await character_handler.update_character(
            mock_valentina_context,
            campaign_api_id="camp-001",
            character_api_id="char-001",
            age=30,
            biography="A dark past",
        )

        # Then: result returned and synced to DB
        assert result.name == "Updated Name"
        assert await DBCharacter.filter(api_id="char-001").count() == 1

    async def test_none_params(self, db, fake_vclient, mock_valentina_context):
        """Verify handler works with no optional fields."""
        # Given: a campaign exists
        await DBCampaign.create(api_id="camp-001", name="Test Campaign")
        character = CharacterFactory.build(id="char-001", campaign_id="camp-001")
        fake_vclient.add_route("PATCH", Endpoints.CHARACTER, json=character.model_dump(mode="json"))

        # When: updating with no optional fields
        result = await character_handler.update_character(
            mock_valentina_context,
            campaign_api_id="camp-001",
            character_api_id="char-001",
        )

        # Then: handler completes without error
        assert result.id == "char-001"

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
        self, db, fake_vclient, mock_valentina_context, mocker, trigger_field
    ):
        """Verify channel manager called when name, status, or type changes."""
        # Given: a campaign exists
        await DBCampaign.create(api_id="camp-001", name="Test Campaign")
        character = CharacterFactory.build(id="char-001", campaign_id="camp-001")
        fake_vclient.add_route("PATCH", Endpoints.CHARACTER, json=character.model_dump(mode="json"))

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
        self, db, fake_vclient, mock_valentina_context, mocker
    ):
        """Verify channel manager not called when only non-trigger fields change."""
        # Given: a campaign exists
        await DBCampaign.create(api_id="camp-001", name="Test Campaign")
        character = CharacterFactory.build(id="char-001", campaign_id="camp-001")
        fake_vclient.add_route("PATCH", Endpoints.CHARACTER, json=character.model_dump(mode="json"))

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
        self, db, fake_vclient, mock_valentina_context, mocker
    ):
        """Verify channel manager skipped when campaign has no DB record."""
        # Given: the campaign does NOT exist in DB
        character = CharacterFactory.build(id="char-001", campaign_id="camp-missing")
        fake_vclient.add_route("PATCH", Endpoints.CHARACTER, json=character.model_dump(mode="json"))

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
        self, db, fake_vclient, mock_valentina_context, mocker
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

        # Given: the API accepts the delete
        fake_vclient.add_route("DELETE", Endpoints.CHARACTER, json={}, status_code=204)

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

        # Then: channel was deleted
        mock_cm_cls.assert_called_once_with(guild=mock_valentina_context.guild)
        mock_cm_instance.delete_character_channel.assert_awaited_once()

        # Then: DB record is removed
        assert await DBCharacter.filter(api_id="char-001").count() == 0

    async def test_no_channel_delete_when_character_not_in_db(
        self, db, fake_vclient, mock_valentina_context, mocker
    ):
        """Verify channel manager skipped when character has no DB record."""
        # Given: the API accepts the delete
        fake_vclient.add_route("DELETE", Endpoints.CHARACTER, json={}, status_code=204)

        # Given: ChannelManager is mocked
        mock_cm_cls = mocker.patch("vbot.handlers.character.ChannelManager", autospec=True)

        # When: deleting a character that only exists in the API (not in DB)
        await character_handler.delete_character(
            mock_valentina_context,
            user_api_id="user-001",
            campaign_api_id="camp-001",
            character_api_id="char-999",
        )

        # Then: ChannelManager was never instantiated
        mock_cm_cls.assert_not_called()
