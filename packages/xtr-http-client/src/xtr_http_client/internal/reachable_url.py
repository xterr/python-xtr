"""A URL written the way the host it names is reached."""

from __future__ import annotations

import httpx

from .httpx_errors import transport_error

__all__ = ["reachable_url"]


def reachable_url(url: str) -> str:
    """``url`` with every part of it written in the form that reaches it.

    A host named in another script is looked up in its ``xn--`` form, which
    is also the only form a message request will hold, so the conversion
    happens here — while the URL is still text — rather than further in,
    where it would surface as a URL nobody can parse.

    Raises:
        InvalidArgumentError: When the URL cannot be read at all.
    """
    if url.isascii():
        return url

    try:
        parsed = httpx.URL(url)

        return str(parsed.copy_with(host=parsed.raw_host.decode("ascii")))
    except (httpx.InvalidURL, UnicodeError) as error:
        raise transport_error(httpx.InvalidURL(str(error)), url) from error
