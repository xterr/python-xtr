"""Parameters written out as a query string, and merged into one a URL carries."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Final, cast
from urllib.parse import quote, quote_plus, unquote_plus

from xtr_http_client.exception import InvalidArgumentError
from xtr_http_client.internal.debug_type import debug_type

if TYPE_CHECKING:
    from collections.abc import Iterator

    from xtr_http_client_contracts import QueryValue

__all__ = ["build_query", "merge_query_string"]

_READABLE: Final = {
    "%21": "!",
    "%24": "$",
    "%28": "(",
    "%29": ")",
    "%2A": "*",
    "%2F": "/",
    "%3A": ":",
    "%3B": ";",
    "%40": "@",
    "%5B": "[",
    "%5D": "]",
}
"""Characters a query string is allowed to carry as themselves.

Every one of them is legal in a query, and browsers leave them alone, so
encoding them would make a URL that works harder to read and harder to
compare with the one a caller wrote.
"""


def build_query(params: Mapping[str, QueryValue], *, option: str, form: bool = False) -> str:
    """Write parameters out as one query string.

    A scalar becomes one parameter. A sequence repeats the name, which is how
    a list is sent to anything that reads repeated names. A mapping names its
    sub-keys in brackets, which is how a nested structure survives a flat
    query string. ``None`` is not sent at all.

    Args:
        params: The parameters to write out.
        option: The name of the option they came from, for the message when
            one of them cannot be written out.
        form: Write a form body rather than a query string, which differs in
            one place: a space becomes ``+``.

    Raises:
        InvalidArgumentError: When a value is neither a scalar, a sequence nor
            a mapping, and so has no unambiguous way of being written out.
    """
    return "&".join(build_pairs(params, option=option, form=form).values())


def build_pairs(
    params: Mapping[str, QueryValue],
    *,
    option: str,
    form: bool = False,
) -> dict[str, str]:
    """The written-out parameters, keyed by the name they are sent under.

    Keyed so that merging can tell one name from another: the parameters a
    URL already carries and the ones being merged in meet by name. A name a
    sequence repeated keeps all of its values under that one key, because
    they belong together — dropping one would change what is being asked for,
    while a *different* parameter of the same name replaces it.
    """
    pairs: dict[str, str] = {}

    for key, value in params.items():
        repeated: dict[str, str] = {}
        for name, raw in _flatten(str(key), value, option):
            written = f"{_encode(name, form=form)}={_encode(raw, form=form)}"
            repeated[name] = f"{repeated[name]}&{written}" if name in repeated else written
        pairs.update(repeated)

    return pairs


def merge_query_string(
    query_string: str | None,
    query_array: Mapping[str, QueryValue],
    *,
    replace: bool,
) -> str | None:
    """Merge parameters into the query string a URL already carries.

    Who wins is the caller's decision. A request's own parameters replace what
    its URL carried — that is what asking for them means. A client's defaults
    only fill in what the URL left out, so a URL can always override them.

    A parameter of ``None`` is not sent, and when replacing it also drops the
    one the URL carried: that is how a default is taken back off.

    Args:
        query_string: The query the URL carries, without its ``?``.
        query_array: The parameters to merge in.
        replace: Whether these parameters win over the ones already there.

    Returns:
        The merged query string without its ``?``, or ``query_string``
        untouched when there is nothing to merge in.
    """
    if not query_array:
        return query_string

    carried = _carried(query_string)
    if replace:
        for name, value in query_array.items():
            if value is None:
                _ = carried.pop(str(name), None)

    merged = dict(carried)
    for name, written in build_pairs(query_array, option="query").items():
        if replace:
            merged[name] = written
        else:
            _ = merged.setdefault(name, written)

    return "&".join(merged.values())


def _carried(query_string: str | None) -> dict[str, str]:
    carried: dict[str, str] = {}
    if query_string is None:
        return carried

    for parameter in query_string.split("&"):
        if parameter == "":
            continue
        name = unquote_plus(parameter.split("=", 1)[0])
        carried[name] = f"{carried[name]}&{parameter}" if name in carried else parameter

    return carried


def _flatten(name: str, value: object, option: str) -> Iterator[tuple[str, str]]:
    if value is None:
        return
    if isinstance(value, Mapping):
        for key, nested in cast("Mapping[object, object]", value).items():
            yield from _flatten(f"{name}[{key}]", nested, option)
        return
    if isinstance(value, str):
        yield name, value
        return
    if isinstance(value, bool):
        yield name, "1" if value else "0"
        return
    if isinstance(value, int | float):
        yield name, str(value)
        return
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        for item in value:
            yield from _flatten(name, item, option)
        return

    raise InvalidArgumentError(
        f'Invalid value for option "{option}": "{debug_type(value)}" is not a scalar, '
        f"a sequence or a mapping."
    )


def _encode(text: str, *, form: bool) -> str:
    if form:
        # A form body escapes a tilde, a query string does not; both come from
        # what a server reading them back expects, not from the characters.
        return quote_plus(text, safe="").replace("~", "%7E")

    encoded = quote(text, safe="")
    if "%" not in encoded:
        return encoded

    for escape, character in _READABLE.items():
        encoded = encoded.replace(escape, character)
    return encoded
