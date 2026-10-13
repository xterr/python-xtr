"""What a request asked for, over what its client always asks for."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from xtr_http_client.exception import InvalidArgumentError
from xtr_http_client.internal.headers import normalize_headers
from xtr_http_client.internal.url import parse_url

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = ["merge_default_options"]


def merge_default_options(
    client_name: str,
    options: Mapping[str, object],
    default_options: Mapping[str, object],
    *,
    allow_extra_options: bool = False,
) -> dict[str, object]:
    """Merge what a request asked for over what its client always asks for.

    An option the request named wins whole — there is no merging *inside* an
    option, because half a timeout or half a body means nothing. Headers are
    the exception, and merge by name: a default header the request did not
    mention is still sent, which is what makes a client-wide ``User-Agent``
    work, while one it did mention is the request's.

    ``query`` is never inherited. A default query belongs to the base URI it
    was configured next to, and only
    :func:`resolve_url <xtr_http_client.internal.url.resolve_url>` knows
    whether this request is going there.

    An option this client does not know is refused rather than ignored, with
    the closest names it does know, since a misspelled option that is quietly
    dropped is a setting that silently never applied.

    Args:
        client_name: The client the options are for, named in the message when
            one of them is not supported.
        options: What the request asked for.
        default_options: What the client always asks for, and the list of what
            it understands at all.
        allow_extra_options: Accept names the client does not know, for a
            decorator that passes options on to a client it does not know the
            shape of.

    Returns:
        Every option, plus ``normalized_headers`` and the ``headers`` lines
        built from it.

    Raises:
        InvalidArgumentError: When an option is not one this client knows, or
            a header cannot be normalized.
    """
    merged: dict[str, object] = dict(options)
    normalized = normalize_headers(_headers(options))
    for name, lines in normalize_headers(_headers(default_options)).items():
        _ = normalized.setdefault(name, lines)
    merged["normalized_headers"] = normalized
    merged["headers"] = [line for lines in normalized.values() for line in lines]

    if options.get("resolve"):
        merged["resolve"] = _pinned(options["resolve"])
    if merged.get("query") is None:
        merged["query"] = {}

    for name, value in default_options.items():
        _ = merged.setdefault(name, value)

    if "extra" in default_options:
        merged["extra"] = _filled(merged.get("extra"), default_options["extra"])
    if default_options.get("resolve"):
        merged["resolve"] = _filled(merged.get("resolve"), _pinned(default_options["resolve"]))

    if not allow_extra_options and default_options:
        _refuse_unsupported(client_name, merged, default_options)

    return merged


def _headers(options: Mapping[str, object]) -> Mapping[str, str | Sequence[str]] | Sequence[str]:
    # Headers reach here through `RequestOptions`, which is what types them;
    # `normalize_headers` is what refuses a value of any other shape.
    return cast("Mapping[str, str | Sequence[str]]", options.get("headers") or {})


def _pinned(resolve: object) -> dict[str, str | None]:
    """Key pinned addresses by the host as a URL would name it.

    The host a request is made to has been lowered, had its default port
    dropped and been turned into ASCII by the time an address is looked up,
    so the pins have to be keyed the same way or none of them would ever be
    found. An address of nothing takes a pin back off, and the brackets an
    IPv6 address is written with in a URL are not part of the address.
    """
    pins: dict[str, str | None] = {}
    for host, address in cast("Mapping[str, str]", resolve).items():
        authority = parse_url(f"http://{host}").authority or "//"
        pins[authority[2:]] = _address(str(address))

    return pins


def _address(address: str) -> str | None:
    if address == "":
        return None
    if address.startswith("[") and address.endswith("]") and ":" in address:
        return address[1:-1]
    return address


def _filled(given: object, defaults: object) -> dict[str, object]:
    filled: dict[str, object] = dict(cast("Mapping[str, object]", given or {}))
    for name, value in cast("Mapping[str, object]", defaults).items():
        _ = filled.setdefault(name, value)

    return filled


def _refuse_unsupported(
    client_name: str,
    merged: Mapping[str, object],
    default_options: Mapping[str, object],
) -> None:
    for name in merged:
        if name in default_options or name == "normalized_headers":
            continue

        alternatives = [
            known
            for known in default_options
            if _levenshtein(name, known) <= len(name) / 3 or name in known
        ]
        did_you_mean = '", "'.join(alternatives or list(default_options))
        raise InvalidArgumentError(
            f'Unsupported option "{name}" passed to "{client_name}", did you mean "{did_you_mean}"?'
        )


def _levenshtein(name: str, known: str) -> int:
    """How many single-character edits apart two option names are."""
    previous = list(range(len(known) + 1))
    for row, character in enumerate(name, start=1):
        current = [row]
        for column, other in enumerate(known, start=1):
            substitution = previous[column - 1] + (character != other)
            current.append(min(previous[column] + 1, current[column - 1] + 1, substitution))
        previous = current

    return previous[-1]
