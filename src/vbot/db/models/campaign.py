"""Campaign model."""

from typing import TYPE_CHECKING

from tortoise import fields
from tortoise.models import Model

from vbot.constants import EmojiDict

from .api import DBUser

if TYPE_CHECKING:
    from tortoise.queryset import QuerySet


class DBCharacter(Model):
    """Character model."""

    id = fields.IntField(primary_key=True)
    api_id = fields.CharField(
        max_length=50, description="The ID of the character in the API.", index=True
    )

    name = fields.CharField(max_length=255, description="The name of the character.", null=True)
    type = fields.CharField(max_length=50, description="The type of the character.")
    status = fields.CharField(max_length=50, description="The status of the character.", null=True)

    user_player_api_id = fields.CharField(
        max_length=50,
        description="The API ID of the user who is the player of the character.",
        null=True,
    )
    user_creator_api_id = fields.CharField(
        max_length=50, description="The API ID of the user who created the character.", null=True
    )

    character_channel_id = fields.IntField(
        description="The discord channel ID of the character channel.", null=True
    )

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    if TYPE_CHECKING:
        campaign: "DBCampaign"
    else:
        campaign: fields.ForeignKeyRelation["DBCampaign"] = fields.ForeignKeyField(
            "vbot.DBCampaign",
            related_name="characters",
            on_delete=fields.OnDelete.SET_NULL,
            null=True,
        )

    def get_channel_name(self) -> str:
        """Get the channel name for the character."""
        if self.type == "STORYTELLER":
            emoji = (
                EmojiDict.CHANNEL_PLAYER
                if self.status == "ALIVE"
                else EmojiDict.CHANNEL_PLAYER_DEAD
            )
            return f"{EmojiDict.CHANNEL_PRIVATE}{emoji}-{self.name.lower().replace(' ', '-')}"

        emoji = (
            EmojiDict.CHANNEL_PLAYER if self.status == "ALIVE" else EmojiDict.CHANNEL_PLAYER_DEAD
        )
        return f"{emoji}-{self.name.lower().replace(' ', '-')}"

    async def get_user_player_discord_id(self) -> int | None:
        """Get the Discord ID of the user who is the player of the character."""
        if not self.user_player_api_id:
            return None

        user = await DBUser.get_or_none(api_user_id=self.user_player_api_id)
        return user.discord_user_id if user else None


class DBCampaignBook(Model):
    """Campaign book model."""

    id = fields.IntField(primary_key=True)
    api_id = fields.CharField(
        max_length=50, description="The ID of the book in the API.", index=True
    )
    name = fields.CharField(max_length=255, description="The name of the book.", null=True)
    number = fields.IntField(description="The number of the book.", null=True)

    book_channel_id = fields.IntField(
        description="The discord channel ID of the book channel.", null=True
    )

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    if TYPE_CHECKING:
        campaign: "DBCampaign"
    else:
        campaign: fields.ForeignKeyRelation["DBCampaign"] = fields.ForeignKeyField(
            "vbot.DBCampaign",
            related_name="books",
            on_delete=fields.OnDelete.CASCADE,
        )

    def get_channel_name(self) -> str:
        """Get the channel name for the book."""
        return f"{EmojiDict.BOOK}-{self.number:0>2}-{self.name.lower().replace(' ', '-')}"


class DBCampaign(Model):
    """Campaign model."""

    id = fields.IntField(primary_key=True)
    api_id = fields.CharField(
        max_length=50, description="The ID of the campaign in the API.", index=True
    )
    name = fields.CharField(max_length=255, description="The name of the campaign.", null=True)

    category_channel_id = fields.IntField(
        description="The Discord channel ID of the category channel.", null=True
    )
    storyteller_channel_id = fields.IntField(
        description="The Discord channel ID of the storyteller channel.", null=True
    )
    general_channel_id = fields.IntField(
        description="The Discord channel ID of the general channel.", null=True
    )

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    if TYPE_CHECKING:
        books: QuerySet[DBCampaignBook]
        characters: QuerySet[DBCharacter]
    else:
        books: fields.ReverseRelation[DBCampaignBook]
        characters: fields.ReverseRelation[DBCharacter]

    def get_category_channel_name(self) -> str:
        """Get the category channel name for the campaign."""
        return f"{EmojiDict.BOOKS}-{self.name.lower().replace(' ', '-')}"
