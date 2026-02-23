"""Database configuration."""

from .base import settings

DB_CONFIG = {
    "connections": {
        "default": {
            "engine": "tortoise.backends.sqlite",
            "credentials": {"file_path": settings.database_path},
        }
    },
    "apps": {
        "vbot": {
            "models": ["vbot.db.models", "aerich.models"],
            "default_connection": "default",
        },
    },
}
