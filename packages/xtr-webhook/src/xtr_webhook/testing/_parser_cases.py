"""Reading a directory of fixture pairs, and driving a parser over one of them."""

from __future__ import annotations

import runpy
from typing import TYPE_CHECKING, cast

from xtr_http_message import ServerRequest

from xtr_webhook.exception import InvalidArgumentError

from .parser_case import ParserCase

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from xtr_remote_event import RemoteEvent

    from xtr_webhook.client import RequestParserInterface

__all__ = ["assert_parses", "parser_cases"]

_EXPECTATION = "EXPECTED"
_JSON = "application/json"


def parser_cases(fixtures_dir: Path, extension: str = "json") -> list[ParserCase]:
    """Read every fixture pair under ``fixtures_dir`` into a case.

    A pair is a capture — ``*.<extension>``, the bytes as the sender posted
    them — and a ``*.py`` beside it naming ``EXPECTED``: one
    :class:`~xtr_remote_event.RemoteEvent`, or a list of them for a capture
    that carried a batch. The expectation is Python rather than data so it can
    say exactly which events, with the types the parser will produce, instead
    of a second format to agree on.

    The directory is walked recursively, so captures can be grouped by the
    event kind they belong to, and the result is sorted by id, so a run reports
    the same order whatever order the file system hands the files back in.

    Args:
        fixtures_dir: The directory the captures lie under.
        extension: What the captures are named with, without the dot. A sender
            whose captures are not JSON is kept in files named for what they
            are.

    Returns:
        One case per capture, sorted by id.

    Raises:
        InvalidArgumentError: When a capture has no expectation file beside it,
            or that file names no ``EXPECTED``. Either is a pair half-added,
            and silently skipping it would leave a payload nothing ever checks.
    """
    return sorted(
        (_read(capture, fixtures_dir) for capture in fixtures_dir.rglob(f"*.{extension}")),
        key=lambda case: case.id,
    )


async def assert_parses(
    parser: RequestParserInterface,
    case: ParserCase,
    *,
    secret: str = "",
    headers: Mapping[str, str] | None = None,
    method: str = "POST",
) -> None:
    """Post ``case`` to ``parser`` and check it read what the case expects.

    The request is built from the capture's bytes under
    ``Content-Type: application/json``, which is what the matchers of a JSON
    sender's parser look for. A sender that signs its webhooks needs its
    signature headers too, and the secret they were made with::

        await assert_parses(AcmeParser(), case, secret=SECRET, headers=signed(case.payload))

    Args:
        parser: The parser under test.
        case: The pair to drive it over.
        secret: What the parser checks the sender's signature against.
        headers: Headers to send alongside the content type — a signature, a
            timestamp, whatever the sender puts on its webhooks. An entry named
            ``Content-Type`` replaces the default.
        method: The method the sender posts with.

    Raises:
        AssertionError: When the parser read something other than
            ``case.expected``. Raised rather than asserted so the check holds
            however the test suite is run, and carries both sides so the
            difference is in the failure itself.
    """
    request = ServerRequest(
        method,
        "/",
        {"Content-Type": _JSON, **(headers or {})},
        case.payload,
    )

    read = await parser.parse(request, secret)
    if read != case.expected:
        raise AssertionError(f'"{case.id}" was read as {read!r}, not {case.expected!r}.')


def _read(capture: Path, fixtures_dir: Path) -> ParserCase:
    """Pair one capture with the expectation file beside it.

    Args:
        capture: The file holding the bytes the sender posted.
        fixtures_dir: The directory the walk started from, which the case's id
            is relative to.

    Returns:
        The capture and its expectation, as one case.

    Raises:
        InvalidArgumentError: When the expectation file is missing or names no
            ``EXPECTED``.
    """
    expectation = capture.with_suffix(".py")
    if not expectation.is_file():
        raise InvalidArgumentError(
            f'The fixture "{capture}" has no expectation file "{expectation}".'
        )

    # Run rather than import: a capture is grouped by what it is, not by what
    # makes an importable module name, and nothing else reads these files.
    named: dict[str, object] = runpy.run_path(str(expectation))
    if _EXPECTATION not in named:
        raise InvalidArgumentError(
            f'The expectation file "{expectation}" defines no {_EXPECTATION}.'
        )

    return ParserCase(
        capture.relative_to(fixtures_dir).as_posix(),
        capture.read_bytes(),
        # The expectation file states the type; a value of any other kind shows
        # itself as the mismatch it is when the parser is driven over the case.
        cast("RemoteEvent | list[RemoteEvent]", named[_EXPECTATION]),
    )
