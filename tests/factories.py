"""Factory functions for creating vclient Pydantic model instances in tests."""

from __future__ import annotations

from datetime import UTC, datetime

from vclient.models import (
    Campaign,
    CampaignBook,
    CampaignChapter,
    CampaignExperience,
    Character,
    DiscordProfile,
    RollStatistics,
    User,
)


def make_campaign(**overrides) -> Campaign:
    """Create a Campaign instance with sensible defaults."""
    defaults = {
        "id": "campaign-001",
        "date_created": datetime(2024, 1, 1, tzinfo=UTC),
        "date_modified": datetime(2024, 1, 1, tzinfo=UTC),
        "name": "Test Campaign",
        "description": "A test campaign",
        "company_id": "company-001",
        "desperation": 0,
        "danger": 0,
    }
    defaults.update(overrides)
    return Campaign(**defaults)


def make_user(**overrides) -> User:
    """Create a User instance with sensible defaults including a DiscordProfile."""
    defaults = {
        "id": "user-001",
        "date_created": datetime(2024, 1, 1, tzinfo=UTC),
        "date_modified": datetime(2024, 1, 1, tzinfo=UTC),
        "username": "testuser",
        "name_first": "Test",
        "name_last": "User",
        "email": "test@example.com",
        "role": "PLAYER",
        "company_id": "company-001",
        "discord_profile": DiscordProfile(
            id="123456789",
            username="testuser",
            global_name="Test User",
            discriminator="0",
        ),
    }
    defaults.update(overrides)
    return User(**defaults)


def make_campaign_book(**overrides) -> CampaignBook:
    """Create a CampaignBook instance with sensible defaults."""
    defaults = {
        "id": "book-001",
        "date_created": datetime(2024, 1, 1, tzinfo=UTC),
        "date_modified": datetime(2024, 1, 1, tzinfo=UTC),
        "name": "Test Book",
        "number": 1,
        "campaign_id": "campaign-001",
    }
    defaults.update(overrides)
    return CampaignBook(**defaults)


def make_character(**overrides) -> Character:
    """Create a Character instance with sensible defaults."""
    defaults = {
        "id": "char-001",
        "date_created": datetime(2024, 1, 1, tzinfo=UTC),
        "date_modified": datetime(2024, 1, 1, tzinfo=UTC),
        "character_class": "VAMPIRE",
        "type": "PLAYER",
        "game_version": "V5",
        "status": "ALIVE",
        "name_first": "John",
        "name_last": "Doe",
        "name": "John Doe",
        "name_full": "John Doe",
        "user_creator_id": "user-001",
        "user_player_id": "user-001",
        "company_id": "company-001",
        "campaign_id": "campaign-001",
    }
    defaults.update(overrides)
    return Character(**defaults)


def make_roll_statistics(**overrides) -> RollStatistics:
    """Create a RollStatistics instance with sensible defaults."""
    defaults = {
        "botches": 2,
        "successes": 5,
        "failures": 3,
        "criticals": 1,
        "total_rolls": 11,
        "criticals_percentage": 9.09,
        "success_percentage": 45.45,
        "failure_percentage": 27.27,
        "botch_percentage": 18.18,
    }
    defaults.update(overrides)
    return RollStatistics(**defaults)


def make_campaign_experience(**overrides) -> CampaignExperience:
    """Create a CampaignExperience instance with sensible defaults."""
    defaults = {
        "campaign_id": "campaign-001",
        "xp_current": 10,
        "xp_total": 25,
        "cool_points": 3,
    }
    defaults.update(overrides)
    return CampaignExperience(**defaults)


def make_chapter(**overrides) -> CampaignChapter:
    """Create a CampaignChapter instance with sensible defaults."""
    defaults = {
        "id": "chapter-001",
        "date_created": datetime(2024, 1, 1, tzinfo=UTC),
        "date_modified": datetime(2024, 1, 1, tzinfo=UTC),
        "name": "Test Chapter",
        "number": 1,
        "book_id": "book-001",
    }
    defaults.update(overrides)
    return CampaignChapter(**defaults)
