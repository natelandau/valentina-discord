"""Tests for network utility functions."""

from __future__ import annotations

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vbot.lib.exceptions import URLNotAvailableError
from vbot.utils.network import fetch_data_from_url

pytestmark = pytest.mark.anyio


def _build_mocks(status: int, content: bytes = b"") -> MagicMock:
    """Build nested async-context-manager mocks for ClientSession.

    aiohttp's `session.get(url)` returns a sync object (not a coroutine) that
    implements `__aenter__`/`__aexit__`, so `get` must be a regular callable
    (MagicMock) whose return value is an async context manager.
    """
    mock_resp = AsyncMock()
    mock_resp.status = status
    mock_resp.read = AsyncMock(return_value=content)

    # session.get(url) returns an async CM, not a coroutine
    mock_get_cm = AsyncMock()
    mock_get_cm.__aenter__.return_value = mock_resp

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=mock_get_cm)

    mock_cls = MagicMock()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

    return mock_cls


class TestFetchDataFromUrl:
    """Tests for fetch_data_from_url()."""

    async def test_success_returns_bytesio(self):
        """Verify successful fetch returns BytesIO with response content."""
        # Given: a mock response with status 200 and known content
        content = b"fake image data"
        mock_cls = _build_mocks(status=200, content=content)

        with patch("vbot.utils.network.ClientSession", mock_cls):
            # When: fetching data from a URL
            result = await fetch_data_from_url("https://example.com/image.png")

        # Then: result is a BytesIO containing the response content
        assert isinstance(result, io.BytesIO)
        assert result.read() == content

    async def test_non_200_raises_url_not_available(self):
        """Verify non-200 status raises URLNotAvailableError."""
        # Given: a mock response with status 404
        mock_cls = _build_mocks(status=404)

        with (
            patch("vbot.utils.network.ClientSession", mock_cls),
            pytest.raises(URLNotAvailableError, match="Could not fetch data"),
        ):
            # When/Then: fetching raises URLNotAvailableError
            await fetch_data_from_url("https://example.com/missing.png")

    async def test_server_error_raises_url_not_available(self):
        """Verify server error status raises URLNotAvailableError."""
        # Given: a mock response with status 500
        mock_cls = _build_mocks(status=500)

        with (
            patch("vbot.utils.network.ClientSession", mock_cls),
            pytest.raises(URLNotAvailableError),
        ):
            # When/Then: fetching raises URLNotAvailableError
            await fetch_data_from_url("https://example.com/error")
