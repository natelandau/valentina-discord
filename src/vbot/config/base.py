"""Instantiate settings default values."""

from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from vbot.constants import ENVAR_PREFIX, LogLevel

__all__ = ("settings",)


def string_to_list(value: str) -> list[str]:
    """Convert a comma-separated string to a list of strings."""
    return [x.strip() for x in value.split(",")]


class DiscordSettings(BaseModel):
    """Discord settings."""

    guilds: Annotated[
        list[str], Field(default_factory=list), BeforeValidator(string_to_list), NoDecode
    ]
    owner_channels: Annotated[
        list[str], Field(default_factory=list), BeforeValidator(string_to_list), NoDecode
    ]
    owner_ids: Annotated[
        list[str], Field(default_factory=list), BeforeValidator(string_to_list), NoDecode
    ]
    token: str


class VClientSettings(BaseModel):
    """VClient settings."""

    base_url: str
    api_key: str
    default_company_id: str
    timeout: float = Field(default=10.0)
    max_retries: int = Field(default=5)
    retry_delay: float = Field(default=1.0)
    auto_retry_rate_limit: bool = Field(default=True)
    auto_idempotency_keys: bool = Field(default=True)
    enable_logs: bool = Field(default=False)


class Settings(BaseSettings):
    """Settings for the application."""

    model_config = SettingsConfigDict(
        env_prefix=ENVAR_PREFIX,
        extra="ignore",
        case_sensitive=False,
        env_file=[".env.secret"],
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
    )

    discord: DiscordSettings
    api: VClientSettings

    database_path: Path = Field(
        description="The path to the sqlite database file.",
        default=Path("data/database.db"),
    )

    log_file_path: Path | None = Field(
        description="The path to the log file.",
        default=None,
    )
    log_level: LogLevel = Field(default=LogLevel.INFO)


settings = Settings()  # type: ignore [call-arg]
