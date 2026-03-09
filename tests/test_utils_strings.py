"""Tests for string utility functions."""

from __future__ import annotations

import pytest
from vclient.testing import CampaignExperienceFactory, RollStatisticsFactory

from vbot.utils.strings import (
    convert_int_to_emoji,
    experience_to_markdown,
    num_to_circles,
    statistics_to_markdown,
    truncate_string,
)


class TestNumToCircles:
    """Tests for num_to_circles()."""

    @pytest.mark.parametrize(
        ("num", "maximum", "expected"),
        [
            (0, 5, "○○○○○"),
            (3, 5, "●●●○○"),
            (5, 5, "●●●●●"),
            (7, 5, "●●●●●●●"),
            (0, 0, ""),
            (None, 5, "○○○○○"),
            (3, None, "●●●○○"),
        ],
    )
    def test_num_to_circles(self, num, maximum, expected):
        """Verify circle string matches expected output for various inputs."""
        assert num_to_circles(num, maximum) == expected


class TestTruncateString:
    """Tests for truncate_string()."""

    @pytest.mark.parametrize(
        ("text", "max_length", "expected"),
        [
            ("short", 1000, "short"),
            ("exact", 5, "exact"),
            ("this is too long", 10, "this i..."),
            ("", 1000, ""),
        ],
    )
    def test_truncate_string(self, text, max_length, expected):
        """Verify truncation behavior at various lengths."""
        assert truncate_string(text, max_length) == expected


class TestConvertIntToEmoji:
    """Tests for convert_int_to_emoji()."""

    @pytest.mark.parametrize(
        ("num", "expected"),
        [
            (0, "0️⃣"),
            (1, "1️⃣"),
            (5, "5️⃣"),
            (10, "🔟"),
        ],
    )
    def test_unicode_emoji(self, num, expected):
        """Verify integers 0-10 return correct unicode emoji."""
        assert convert_int_to_emoji(num=num) == expected

    @pytest.mark.parametrize(
        ("num", "expected"),
        [
            (0, ":zero:"),
            (5, ":five:"),
            (10, ":keycap_ten:"),
        ],
    )
    def test_shortcode(self, num, expected):
        """Verify shortcode mode returns correct discord shortcodes."""
        assert convert_int_to_emoji(num=num, as_shortcode=True) == expected

    def test_out_of_range(self):
        """Verify out-of-range integers return string representation."""
        assert convert_int_to_emoji(num=11) == "11"
        assert convert_int_to_emoji(num=-1) == "-1"

    def test_out_of_range_shortcode(self):
        """Verify out-of-range integers return backtick-wrapped string in shortcode mode."""
        assert convert_int_to_emoji(num=15, as_shortcode=True) == "`15`"


class TestStatisticsToMarkdown:
    """Tests for statistics_to_markdown()."""

    def test_with_data(self):
        """Verify markdown output contains all statistic fields."""
        stats = RollStatisticsFactory.build(
            total_rolls=11,
            botches=2,
            successes=5,
            failures=3,
            criticals=1,
            criticals_percentage=9.09,
            success_percentage=45.45,
            failure_percentage=27.27,
            botch_percentage=18.18,
        )
        result = statistics_to_markdown(stats)

        assert "Total Rolls" in result
        assert "11" in result
        assert "Critical Success" in result
        assert "Successful Rolls" in result
        assert "Failed Rolls" in result
        assert "Botched Rolls" in result

    def test_zero_rolls(self):
        """Verify zero-roll statistics return 'No statistics found' message."""
        stats = RollStatisticsFactory.build(
            total_rolls=0,
            botches=0,
            successes=0,
            failures=0,
            criticals=0,
            criticals_percentage=0,
            success_percentage=0,
            failure_percentage=0,
            botch_percentage=0,
        )
        assert statistics_to_markdown(stats) == "No statistics found"

    def test_with_help(self):
        """Verify help text is appended when with_help=True."""
        stats = RollStatisticsFactory.build(total_rolls=1)
        result = statistics_to_markdown(stats, with_help=True)

        assert "Definitions:" in result
        assert "Critical Success" in result
        assert "Botch" in result


class TestExperienceToMarkdown:
    """Tests for experience_to_markdown()."""

    def test_with_data(self):
        """Verify markdown output contains all experience fields."""
        exp = CampaignExperienceFactory.build(xp_current=10, xp_total=25, cool_points=3)
        result = experience_to_markdown(exp)

        assert "Current XP:  10" in result
        assert "Lifetime CP: 3" in result
        assert "Lifetime XP: 25" in result
        assert result.startswith("```scala")
        assert result.endswith("```")
