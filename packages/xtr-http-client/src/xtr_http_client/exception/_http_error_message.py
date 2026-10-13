"""What an unsuccessful status says it means, read off the response."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import TYPE_CHECKING, Final, cast

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_client_contracts import ResponseInterface

__all__ = ["build_message"]

_MAX_ERROR_BODY: Final = 32768
"""How much of an error document is worth reading to name the error.

An error message is a line or two; a body larger than this is a payload that
happens to have failed, and reading it to the end to quote 40 characters of it
would mean holding it all. Past the limit the status line stands on its own.
"""

_HYDRA: Final = ("hydra:title", "hydra:description")
_PROBLEM: Final = ("title", "detail")
_JSON_WORD: Final = re.compile(r"\bjson\b", re.IGNORECASE)


async def build_message(response: ResponseInterface) -> str:
    """Say what the status means for the request that got it.

    The code and the URL are always enough — ``HTTP 404 returned for "..."``.
    Two things make it better, and both come off the response itself: the
    status line the server sent, which carries its own wording of the code,
    and an error document, which carries the server's wording of the problem.

    The document is only looked for when the head says the body is JSON, and
    only the head of it is parsed, so naming an error never means holding a
    payload. The two shapes read are the ones APIs actually send: ``title`` and
    ``detail``, or the same pair under a ``hydra:`` prefix. The media type is
    not checked beyond "it says JSON" because these shapes travel under many of
    them.

    Args:
        response: The response the status came on. Its body is read with
            ``throw=False``, so reading it cannot raise over the very status
            this message is about.

    Returns:
        The message, ready to be the ``reason`` of an
        :class:`HttpError <xtr_http_client_contracts.exception.http_error.HttpError>`.
    """
    url = response.get_info("url")
    message = f'HTTP {response.get_info("http_code")} returned for "{url}".'
    status_line, is_json = _read_head(response.get_info("response_headers"))

    if status_line is not None:
        message = f'{status_line} returned for "{url}".'
    if not is_json:
        return message

    content = (await response.get_content(throw=False))[:_MAX_ERROR_BODY]
    try:
        document = cast("object", json.loads(content))
    except ValueError:
        return message

    return _described(document) or message


def _read_head(response_headers: object) -> tuple[str | None, bool]:
    """Find the last status line, and whether its response said JSON.

    Read backwards, because a chain of redirects leaves every hop's head in
    there and it is the last one the status belongs to. A content type is
    noted wherever it appears, since it may be written before the status line
    it belongs to.
    """
    if not isinstance(response_headers, Sequence) or isinstance(response_headers, str):
        return None, False

    status_line: str | None = None
    is_json = False
    for line in reversed([entry for entry in response_headers if isinstance(entry, str)]):
        if line.startswith("HTTP/"):
            if status_line is not None:
                break
            status_line = line
        if line.lower().startswith("content-type:"):
            is_json = is_json or _JSON_WORD.search(line) is not None
            if status_line is not None:
                break

    return status_line, is_json


def _described(document: object) -> str | None:
    """Join the two fields an error document names the problem with."""
    if not document or not isinstance(document, dict):
        return None

    # A decoded JSON object is keyed by strings; the cast says so once rather
    # than at every lookup below.
    fields = cast("Mapping[str, object]", document)
    for title, detail in (_HYDRA, _PROBLEM):
        head, tail = fields.get(title), fields.get(detail)
        if head is None and tail is None:
            continue
        if not _is_scalar(head) or not _is_scalar(tail):
            return None
        separator = "\n\n" if head is not None and tail is not None else ""
        return f"{_as_text(head)}{separator}{_as_text(tail)}"

    return None


def _is_scalar(value: object) -> bool:
    """Tell whether a decoded JSON value can stand in a message as it is."""
    return value is None or isinstance(value, str | int | float | bool)


def _as_text(value: object) -> str:
    """Write a scalar out the way the document meant it to be read."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else ""
    return str(value)
