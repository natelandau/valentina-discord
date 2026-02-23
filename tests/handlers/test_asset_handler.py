"""Tests for asset deletion handler."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from vclient.models import Asset

from vbot.db.models import DBCampaign, DBCampaignBook, DBCharacter
from vbot.handlers.assets import delete_asset_handler

pytestmark = pytest.mark.anyio


class _AsyncIter:
    """Wrap a list into an async iterator for use with ``async for``."""

    def __init__(self, items: list):
        self._items = items

    def __aiter__(self):
        self._index = 0
        return self

    async def __anext__(self):
        if self._index >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._index]
        self._index += 1
        return item


def _make_asset(**overrides) -> Asset:
    """Create an Asset instance with sensible defaults."""
    defaults = {
        "id": "asset-001",
        "date_created": datetime(2024, 1, 1, tzinfo=UTC),
        "date_modified": datetime(2024, 1, 1, tzinfo=UTC),
        "asset_type": "image",
        "mime_type": "image/png",
        "original_filename": "test.png",
        "public_url": "https://example.com/test.png",
        "uploaded_by": "user-001",
        "company_id": "company-001",
        "parent_type": "campaign",
        "parent_id": "campaign-001",
    }
    defaults.update(overrides)
    return Asset(**defaults)


class TestDeleteCampaignAsset:
    """Tests for campaign parent type asset deletion."""

    async def test_calls_campaigns_service(self, mocker):
        """Verify campaign asset deletion calls campaigns_service.delete_asset."""
        # Given: a mocked campaigns_service
        service = AsyncMock()
        factory = mocker.patch(
            "vbot.handlers.assets.campaigns_service",
            return_value=service,
        )
        asset = _make_asset(parent_type="campaign", parent_id="campaign-001")

        # When: deleting the asset
        await delete_asset_handler(asset, user_api_id="user-001")

        # Then: campaigns_service was constructed with correct user_id
        factory.assert_called_once_with(user_id="user-001")
        # Then: delete_asset was called with correct IDs
        service.delete_asset.assert_awaited_once_with(
            campaign_id="campaign-001", asset_id="asset-001"
        )


class TestDeleteUserAsset:
    """Tests for user parent type asset deletion."""

    async def test_calls_users_service(self, mocker):
        """Verify user asset deletion calls users_service.delete_asset."""
        # Given: a mocked users_service
        service = AsyncMock()
        factory = mocker.patch(
            "vbot.handlers.assets.users_service",
            return_value=service,
        )
        asset = _make_asset(parent_type="user", parent_id="user-001")

        # When: deleting the asset
        await delete_asset_handler(asset, user_api_id="user-001")

        # Then: users_service was constructed with no args
        factory.assert_called_once_with()
        service.delete_asset.assert_awaited_once_with(user_id="user-001", asset_id="asset-001")


class TestDeleteCharacterAsset:
    """Tests for character parent type asset deletion."""

    async def test_calls_characters_service(self, db, mocker):
        """Verify character asset deletion fetches DB character and calls characters_service."""
        # Given: a campaign and character exist in the DB
        campaign = await DBCampaign.create(api_id="campaign-001", name="Test Campaign")
        await DBCharacter.create(
            api_id="char-001",
            name="Test Char",
            type="PLAYER",
            status="ALIVE",
            campaign=campaign,
        )

        # Given: a mocked characters_service
        service = AsyncMock()
        factory = mocker.patch(
            "vbot.handlers.assets.characters_service",
            return_value=service,
        )
        asset = _make_asset(parent_type="character", parent_id="char-001")

        # When: deleting the asset
        await delete_asset_handler(asset, user_api_id="user-001")

        # Then: characters_service was constructed with correct args
        factory.assert_called_once_with(user_id="user-001", campaign_id="campaign-001")
        service.delete_asset.assert_awaited_once_with(character_id="char-001", asset_id="asset-001")

    async def test_not_found_returns_early(self, db, mocker):
        """Verify early return when character not found in DB."""
        # Given: no character exists in the DB
        factory = mocker.patch(
            "vbot.handlers.assets.characters_service",
            return_value=AsyncMock(),
        )
        asset = _make_asset(parent_type="character", parent_id="nonexistent")

        # When: deleting the asset
        await delete_asset_handler(asset, user_api_id="user-001")

        # Then: characters_service was never called
        factory.assert_not_called()


class TestDeleteCampaignBookAsset:
    """Tests for campaignbook parent type asset deletion."""

    async def test_calls_books_service(self, db, mocker):
        """Verify campaignbook asset deletion fetches DB book and calls books_service."""
        # Given: a campaign and book exist in the DB
        campaign = await DBCampaign.create(api_id="campaign-001", name="Test Campaign")
        await DBCampaignBook.create(
            api_id="book-001", name="Test Book", number=1, campaign=campaign
        )

        # Given: a mocked books_service
        service = AsyncMock()
        factory = mocker.patch(
            "vbot.handlers.assets.books_service",
            return_value=service,
        )
        asset = _make_asset(parent_type="campaignbook", parent_id="book-001")

        # When: deleting the asset
        await delete_asset_handler(asset, user_api_id="user-001")

        # Then: books_service was constructed with correct args
        factory.assert_called_once_with(user_id="user-001", campaign_id="campaign-001")
        service.delete_asset.assert_awaited_once_with(book_id="book-001", asset_id="asset-001")

    async def test_not_found_returns_early(self, db, mocker):
        """Verify early return when book not found in DB."""
        # Given: no book exists in the DB
        factory = mocker.patch(
            "vbot.handlers.assets.books_service",
            return_value=AsyncMock(),
        )
        asset = _make_asset(parent_type="campaignbook", parent_id="nonexistent")

        # When: deleting the asset
        await delete_asset_handler(asset, user_api_id="user-001")

        # Then: books_service was never called
        factory.assert_not_called()


class TestDeleteCampaignChapterAsset:
    """Tests for campaignchapter parent type asset deletion."""

    async def test_iterates_to_find_and_delete(self, mocker):
        """Verify campaignchapter asset iterates campaigns/books/chapters to find and delete."""
        # Given: mock objects representing a campaign -> book -> chapter hierarchy
        campaign_mock = MagicMock()
        campaign_mock.id = "campaign-001"

        book_mock = MagicMock()
        book_mock.id = "book-001"

        chapter_mock = MagicMock()
        chapter_mock.id = "chapter-001"

        # Given: service mocks whose iter_all() returns async iterables
        campaigns_svc = MagicMock()
        campaigns_svc.iter_all.return_value = _AsyncIter([campaign_mock])

        books_svc = MagicMock()
        books_svc.iter_all.return_value = _AsyncIter([book_mock])

        chapters_svc = MagicMock()
        chapters_svc.iter_all.return_value = _AsyncIter([chapter_mock])

        # Given: a separate service mock for the deletion call
        delete_svc = AsyncMock()
        call_count = 0

        def chapters_factory(**_kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                return chapters_svc
            return delete_svc

        mocker.patch("vbot.handlers.assets.campaigns_service", return_value=campaigns_svc)
        mocker.patch("vbot.handlers.assets.books_service", return_value=books_svc)
        mocker.patch("vbot.handlers.assets.chapters_service", side_effect=chapters_factory)

        asset = _make_asset(parent_type="campaignchapter", parent_id="chapter-001")

        # When: deleting the asset
        await delete_asset_handler(asset, user_api_id="user-001")

        # Then: delete_asset was called on the second chapters_service instance
        delete_svc.delete_asset.assert_awaited_once_with(
            chapter_id="chapter-001", asset_id="asset-001"
        )


class TestDeleteAssetEdgeCases:
    """Tests for edge case parent types."""

    async def test_unknown_parent_type_does_not_raise(self):
        """Verify unknown parent type logs a warning and does not raise."""
        # Given: an asset with unknown parent type
        asset = _make_asset(parent_type="unknown", parent_id="xxx")

        # When/Then: deleting does not raise
        await delete_asset_handler(asset, user_api_id="user-001")

    async def test_company_parent_type_is_noop(self):
        """Verify company parent type is a no-op (not yet implemented)."""
        # Given: an asset with company parent type
        asset = _make_asset(parent_type="company", parent_id="company-001")

        # When/Then: deleting does not raise
        await delete_asset_handler(asset, user_api_id="user-001")
