"""Tests for configuration utilities."""

from __future__ import annotations

import pytest

from vbot.config.base import string_to_list


class TestStringToList:
    """Tests for string_to_list()."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("a,b,c", ["a", "b", "c"]),
            ("one", ["one"]),
            ("", [""]),
            ("a, b, c", ["a", "b", "c"]),
            ("  x , y , z  ", ["x", "y", "z"]),
        ],
    )
    def test_string_to_list(self, value, expected):
        """Verify comma-separated string conversion with whitespace handling."""
        assert string_to_list(value) == expected

    def test_preserves_internal_spaces(self):
        """Verify internal spaces within items are preserved."""
        result = string_to_list("hello world, foo bar")
        assert result == ["hello world", "foo bar"]
