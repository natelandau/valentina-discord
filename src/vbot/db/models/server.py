"""Server model."""

from tortoise import fields
from tortoise.models import Model


class Server(Model):
    """Server model."""

    id = fields.IntField(primary_key=True)

    guild_id = fields.IntField(description="The ID of the discord server.", null=True)
    name = fields.CharField(
        max_length=255, description="The name of the discord server.", null=True
    )
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    audit_log_channel_id = fields.IntField(
        description="The ID of the audit log channel.", null=True
    )
    error_log_channel_id = fields.IntField(
        description="The ID of the error log channel.", null=True
    )
    changelog_channel_id = fields.IntField(
        description="The ID of the changelog channel.", null=True
    )
    storyteller_channel_id = fields.IntField(
        description="The ID of the storyteller channel.", null=True
    )
