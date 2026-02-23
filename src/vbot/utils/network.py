"""Network utilities."""

from __future__ import annotations

import io

from aiohttp import ClientSession

from vbot.lib import exceptions


async def fetch_data_from_url(url: str) -> io.BytesIO:  # pragma: no cover
    """Fetch data from a URL and return it as a BytesIO object.

    Retrieve data from a specified URL and return it as a BytesIO object, which can be used for further processing or uploading to services like Amazon S3.

    Args:
        url (str): The URL from which to fetch the data.

    Returns:
        io.BytesIO: A BytesIO object containing the fetched data.

    Raises:
        errors.URLNotAvailableError: If the URL cannot be accessed or returns a non-200 status code.
    """
    async with ClientSession() as session, session.get(url) as resp:
        if resp.status != 200:  # noqa: PLR2004
            msg = f"Could not fetch data from {url}"
            raise exceptions.URLNotAvailableError(msg)

        return io.BytesIO(await resp.read())
