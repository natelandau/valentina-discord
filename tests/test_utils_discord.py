"""Tests for Discord utility functions."""

from __future__ import annotations

import discord

from vclient.models import DiscordProfile

from vbot.constants import ChannelPermission
from vbot.db.models import DBCampaign, DBCampaignBook, DBCharacter
from vbot.utils.discord import ChannelObjects, build_discord_profile, set_channel_perms


class TestSetChannelPerms:
    """Tests for set_channel_perms()."""

    def test_hidden(self):
        """Verify HIDDEN maps to all-False permissions."""
        perms = set_channel_perms(ChannelPermission.HIDDEN)

        assert perms.view_channel is False
        assert perms.read_messages is False
        assert perms.send_messages is False
        assert perms.add_reactions is False
        assert perms.manage_messages is False
        assert perms.read_message_history is False

    def test_read_only(self):
        """Verify READ_ONLY allows viewing but not sending."""
        perms = set_channel_perms(ChannelPermission.READ_ONLY)

        assert perms.view_channel is True
        assert perms.read_messages is True
        assert perms.send_messages is False
        assert perms.add_reactions is True
        assert perms.manage_messages is False
        assert perms.read_message_history is True
        assert perms.use_slash_commands is False

    def test_post(self):
        """Verify POST allows viewing and sending."""
        perms = set_channel_perms(ChannelPermission.POST)

        assert perms.view_channel is True
        assert perms.read_messages is True
        assert perms.send_messages is True
        assert perms.add_reactions is True
        assert perms.manage_messages is False
        assert perms.read_message_history is True
        assert perms.use_slash_commands is True

    def test_manage(self):
        """Verify MANAGE allows all permissions."""
        perms = set_channel_perms(ChannelPermission.MANAGE)

        assert perms.view_channel is True
        assert perms.read_messages is True
        assert perms.send_messages is True
        assert perms.add_reactions is True
        assert perms.manage_messages is True
        assert perms.read_message_history is True
        assert perms.use_slash_commands is True

    def test_default(self):
        """Verify DEFAULT returns an empty PermissionOverwrite with no explicit settings."""
        perms = set_channel_perms(ChannelPermission.DEFAULT)

        assert isinstance(perms, discord.PermissionOverwrite)
        # DEFAULT is not in the permission_mapping, so all values remain unset (None)
        assert perms.view_channel is None
        assert perms.send_messages is None

    def test_returns_permission_overwrite(self):
        """Verify return type is always discord.PermissionOverwrite."""
        for perm in ChannelPermission:
            result = set_channel_perms(perm)
            assert isinstance(result, discord.PermissionOverwrite)


class TestChannelObjects:
    """Tests for ChannelObjects dataclass."""

    def test_bool_true_with_campaign(self):
        """Verify __bool__ returns True when campaign is present."""
        obj = ChannelObjects(
            campaign=DBCampaign.construct(name="Test"),
            book=None,
            character=None,
            is_storyteller_channel=False,
        )
        assert bool(obj) is True

    def test_bool_true_with_book(self):
        """Verify __bool__ returns True when book is present."""
        obj = ChannelObjects(
            campaign=None,
            book=DBCampaignBook.construct(name="Test Book"),
            character=None,
            is_storyteller_channel=False,
        )
        assert bool(obj) is True

    def test_bool_true_with_character(self):
        """Verify __bool__ returns True when character is present."""
        obj = ChannelObjects(
            campaign=None,
            book=None,
            character=DBCharacter.construct(name="Test Char"),
            is_storyteller_channel=False,
        )
        assert bool(obj) is True

    def test_bool_false_when_all_none(self):
        """Verify __bool__ returns False when all objects are None."""
        obj = ChannelObjects(
            campaign=None,
            book=None,
            character=None,
            is_storyteller_channel=False,
        )
        assert bool(obj) is False

    def test_bool_false_ignores_storyteller_flag(self):
        """Verify __bool__ ignores is_storyteller_channel flag."""
        obj = ChannelObjects(
            campaign=None,
            book=None,
            character=None,
            is_storyteller_channel=True,
        )
        assert bool(obj) is False


class TestBuildDiscordProfile:
    """Tests for build_discord_profile()."""

    def test_builds_profile_from_member(self, mock_discord_member):
        """Verify all DiscordProfile fields populated from member attributes."""
        # When: building a profile from a discord member
        result = build_discord_profile(mock_discord_member)

        # Then: all fields are set correctly
        assert isinstance(result, DiscordProfile)
        assert result.id == str(mock_discord_member.id)
        assert result.username == mock_discord_member.name
        assert result.global_name == mock_discord_member.global_name
        assert result.avatar_id == str(mock_discord_member.avatar.key)
        assert result.avatar_url == mock_discord_member.avatar.url
        assert result.discriminator == mock_discord_member.discriminator

    def test_handles_no_avatar(self, mock_discord_member):
        """Verify avatar fields are None when member has no avatar."""
        # Given: member has no avatar
        mock_discord_member.avatar = None

        # When: building a profile
        result = build_discord_profile(mock_discord_member)

        # Then: avatar fields are None
        assert result.avatar_id is None
        assert result.avatar_url is None
