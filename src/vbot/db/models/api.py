"""API models for the database."""

from tortoise import fields
from tortoise.models import Model


class DBUser(Model):
    """API User model."""

    discord_user_id = fields.IntField(primary_key=True)
    api_user_id = fields.CharField(
        max_length=50, description="The ID of the user in the API.", index=True, null=True
    )
    email = fields.CharField(max_length=255, description="The email of the user.", null=True)
    role = fields.CharField(max_length=25, default="PLAYER")

    name = fields.CharField(max_length=255, description="The name of the user.", null=True)

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
