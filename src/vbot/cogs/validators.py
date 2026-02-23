"""Validators for the cogs."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import aiohttp
from discord.ext.commands import BadArgument, Converter

from vbot.constants import VALID_IMAGE_EXTENSIONS

if TYPE_CHECKING:
    from discord.ext import commands


class ValidImageURL(Converter):  # pragma: no cover
    """Converter that ensures a requested image URL is valid."""

    async def convert(self, ctx: commands.Context, argument: str) -> str:  # noqa: ARG002
        """Validate and normalize thumbnail URLs."""
        if not re.match(r"^https?://", argument):
            msg = "Thumbnail URLs must start with `http://` or `https://`"
            raise BadArgument(msg)

        # Extract the file extension from the URL
        file_extension = argument.rsplit(".", maxsplit=1)[-1].lower()

        if file_extension not in VALID_IMAGE_EXTENSIONS:
            msg = f"Thumbnail URLs must end with a valid image extension: {', '.join(VALID_IMAGE_EXTENSIONS)}"
            raise BadArgument(msg)

        async with aiohttp.ClientSession() as session, session.get(argument) as r:
            success_status_codes = [200, 201, 202, 203, 204, 205, 206]
            if r.status not in success_status_codes:
                msg = f"Thumbnail URL could not be accessed\nStatus: {r.status}"
                raise BadArgument(msg)

        # Replace media.giphy.com URLs with i.giphy.com URLs
        return re.sub(r"//media\.giphy\.com", "//i.giphy.com", argument)
