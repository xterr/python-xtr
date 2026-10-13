"""What a request asked for, over what its client always asks for."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from xtr_http_client.exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["merge_default_options", "validate_options"]


def merge_default_options(
    client_name: str,
    options: Mapping[str, object],
    default_options: Mapping[str, object],
    *,
    allow_extra_options: bool = False,
) -> dict[str, object]:
    """Merge what a request asked for over what its client always asks for.

    An option the request named wins whole — there is no merging *inside* an
    option, because half a timeout or half a body means nothing. ``extra`` and
    ``resolve`` are the exceptions, and merge by key: an entry the defaults
    carry that the request did not mention is kept, which is what makes a
    client-wide setting work, while one it did mention is the request's.

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
        Every option, the request's over the client's.

    Raises:
        InvalidArgumentError: When an option is not one this client knows.
    """
    merged: dict[str, object] = dict(options)
    for name, value in default_options.items():
        _ = merged.setdefault(name, value)

    if "extra" in default_options:
        merged["extra"] = _filled(merged.get("extra"), default_options["extra"])
    if default_options.get("resolve"):
        merged["resolve"] = _filled(merged.get("resolve"), default_options["resolve"])

    if not allow_extra_options and default_options:
        validate_options(client_name, merged, default_options)

    return merged


def validate_options(
    client_name: str,
    options: Mapping[str, object],
    default_options: Mapping[str, object],
) -> None:
    """Refuse an option this client does not know, naming the closest it does.

    Refused rather than ignored, since a misspelled option that is quietly
    dropped is a setting that silently never applied.

    Args:
        client_name: The client the options are for, named in the message.
        options: The names to check.
        default_options: The list of what the client understands at all.

    Raises:
        InvalidArgumentError: When an option is not one this client knows.
    """
    for name in options:
        if name in default_options:
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


def _filled(given: object, defaults: object) -> dict[str, object]:
    filled: dict[str, object] = dict(cast("Mapping[str, object]", given or {}))
    for name, value in cast("Mapping[str, object]", defaults).items():
        _ = filled.setdefault(name, value)

    return filled


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
