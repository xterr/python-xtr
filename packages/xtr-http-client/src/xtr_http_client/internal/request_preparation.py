"""Everything that happens to a request before a connection is opened."""

from __future__ import annotations

import json
import re
import ssl
from base64 import b64encode
from collections.abc import Sequence
from typing import TYPE_CHECKING, Final, cast

from xtr_http_client.exception import InvalidArgumentError
from xtr_http_client.internal.body import FORM_CONTENT_TYPE, json_encode, normalize_body
from xtr_http_client.internal.debug_type import debug_type
from xtr_http_client.internal.option_merge import merge_default_options
from xtr_http_client.internal.peer_fingerprint import normalize_peer_fingerprint
from xtr_http_client.internal.url import parse_url, resolve_url

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_client_contracts import QueryValue

    from xtr_http_client.url_parts import UrlParts

__all__ = ["prepare_request"]

_DEFAULT_TIMEOUT: Final = 60.0
"""How long a transfer may go quiet for when nobody said.

Long enough for a server that is thinking, short enough that a connection
nothing is coming in on is given up rather than held for the rest of the
process's life.
"""

_UNLIMITED_TIMEOUT: Final = 172800.0
"""What a negative timeout means: two days, which is as good as none."""

_CONTENT_LENGTH: Final = "Content-Length: "
_AUTH_BASIC_PARTS: Final = (1, 2)
_UNPRINTABLE: Final = re.compile(r"[^\x21-\x7E]")
_NO_BODY: Final = (None, b"", "")


def prepare_request(  # noqa: PLR0913 — the upstream shape: what, where, asked, always, and how strict
    client_name: str,
    method: str | None,
    url: str | None,
    options: Mapping[str, object],
    default_options: Mapping[str, object] | None = None,
    *,
    allow_extra_options: bool = False,
) -> tuple[UrlParts | None, dict[str, object]]:
    """Validate a request, merge it with the defaults, and resolve its URL.

    Everything a client has to do before it can open a connection, in one
    place, so every client here does it the same way and a request refused by
    one is refused by all of them. Nothing in here touches the network.

    A method or a URL of ``None`` means "not this request": it is how a client
    prepares its own defaults, which have to go through the same merging and
    normalising without being sent anywhere. The credentials, the base URI and
    the query then stay in the options for the request that will use them.

    Args:
        client_name: The client this is for, named when an option is refused.
        method: The HTTP method, uppercase, or ``None``.
        url: The URL, absolute or relative to ``base_uri``, or ``None``.
        options: What this request asks for.
        default_options: What the client always asks for.
        allow_extra_options: Accept option names the client does not know.

    Returns:
        The resolved URL — ``None`` when none was given — and every option,
        with ``normalized_headers`` and the ``headers`` lines to send.

    Raises:
        InvalidArgumentError: When the method, an option, a header, the body
            or the URL is one this client will not send.
    """
    if method is not None:
        _refuse_bad_method(method)

    merged = merge_default_options(
        client_name,
        options,
        default_options or {},
        allow_extra_options=allow_extra_options,
    )
    # `merge_default_options` always leaves this behind: the lines every step
    # below adds to, and what the flat `headers` list is built from at the end.
    normalized = cast("dict[str, list[str]]", merged["normalized_headers"])

    _check_buffer(merged)
    _apply_json(merged, normalized)
    _ = normalized.setdefault("accept", ["Accept: */*"])
    _apply_body(merged, normalized)
    _announce_form(merged, normalized, method)
    _check_connection(merged)
    _check_auth(merged)

    prepared_url = None
    if url is not None:
        _apply_auth_headers(merged, normalized)
        prepared_url = _resolved(merged, url, default_options or {})

    _apply_numbers(merged)
    merged["headers"] = [line for lines in normalized.values() for line in lines]

    return prepared_url, merged


def _refuse_bad_method(method: str) -> None:
    if method == "":
        raise InvalidArgumentError("The HTTP method cannot be empty.")
    if not (method.isascii() and method.isalpha() and method.isupper()):
        raise InvalidArgumentError(
            f'Invalid HTTP method "{method}", only uppercase letters are accepted.'
        )


def _check_buffer(merged: Mapping[str, object]) -> None:
    buffer = merged.get("buffer", True)
    if not isinstance(buffer, bool) and not callable(buffer):
        raise InvalidArgumentError(
            f'Option "buffer" must be a bool or a callable, "{debug_type(buffer)}" given.'
        )


def _apply_json(merged: dict[str, object], normalized: dict[str, list[str]]) -> None:
    document = merged.get("json")
    if document is None:
        return
    if merged.get("body") not in _NO_BODY:
        raise InvalidArgumentError(
            'Define either the "json" or the "body" option, setting both is not supported.'
        )

    merged["body"] = json_encode(document)
    del merged["json"]
    _ = normalized.setdefault("content-type", ["Content-Type: application/json"])


def _apply_body(merged: dict[str, object], normalized: dict[str, list[str]]) -> None:
    if "body" not in merged:
        return

    body = normalize_body(merged["body"], normalized)
    merged["body"] = body
    if isinstance(body, bytes):
        _fix_content_length(body, normalized)


def _fix_content_length(body: bytes, normalized: dict[str, list[str]]) -> None:
    """Say how long the body is, since only the body knows.

    A length the caller declared is corrected rather than trusted: a server
    reading one more byte than was sent waits for it, and one reading fewer
    starts the next request in the middle of this body.
    """
    lines = normalized.get("content-length")
    declared = lines[0][len(_CONTENT_LENGTH) :] if lines else ""
    if str(len(body)) == declared or (declared == "" and body == b""):
        return

    normalized["content-length"] = [f"{_CONTENT_LENGTH}{len(body)}"]


def _announce_form(
    merged: Mapping[str, object],
    normalized: dict[str, list[str]],
    method: str | None,
) -> None:
    """Say a body nobody described is a form, which is what a server assumes.

    It belongs here rather than in one client because every client has to do
    it: a body with no content type is read as a form by anything that reads
    it at all, so sending one without saying so means the request works
    through one client and not through another.
    """
    has_body = merged.get("body") not in _NO_BODY or method == "POST"
    if (has_body or "content-length" in normalized) and "content-type" not in normalized:
        normalized["content-type"] = [f"Content-Type: {FORM_CONTENT_TYPE}"]


def _check_connection(merged: dict[str, object]) -> None:
    fingerprint = merged.get("peer_fingerprint")
    if fingerprint is not None:
        merged["peer_fingerprint"] = normalize_peer_fingerprint(fingerprint)

    crypto_method = merged.get("crypto_method")
    if crypto_method is not None and not isinstance(crypto_method, ssl.TLSVersion):
        raise InvalidArgumentError(
            f'Option "crypto_method" must be one of the TLS versions, '
            f'"{debug_type(crypto_method)}" given.'
        )

    on_progress = merged.get("on_progress")
    if on_progress is not None and not callable(on_progress):
        raise InvalidArgumentError(
            f'Option "on_progress" must be callable, "{debug_type(on_progress)}" given.'
        )


def _check_auth(merged: dict[str, object]) -> None:
    basic = merged.get("auth_basic")
    if isinstance(basic, Sequence) and not isinstance(basic, str):
        if len(basic) not in _AUTH_BASIC_PARTS:
            raise InvalidArgumentError(
                f'Option "auth_basic" must contain 1 or 2 elements, "{len(basic)}" given.'
            )
        basic = ":".join(str(part) for part in basic)
        merged["auth_basic"] = basic

    if basic is not None and not isinstance(basic, str):
        raise InvalidArgumentError(
            f'Option "auth_basic" must be a string or a tuple, "{debug_type(basic)}" given.'
        )

    bearer = merged.get("auth_bearer")
    if bearer is not None:
        _check_bearer(bearer)
    if basic is not None and bearer is not None:
        raise InvalidArgumentError(
            'Define either the "auth_basic" or the "auth_bearer" option, '
            "setting both is not supported."
        )


def _check_bearer(bearer: object) -> None:
    if not isinstance(bearer, str):
        raise InvalidArgumentError(
            f'Option "auth_bearer" must be a string, "{debug_type(bearer)}" given.'
        )
    if _UNPRINTABLE.search(bearer):
        raise InvalidArgumentError(
            f'Invalid character found in option "auth_bearer": {json.dumps(bearer)}.'
        )


def _apply_auth_headers(merged: dict[str, object], normalized: dict[str, list[str]]) -> None:
    """Turn the credentials into the header that carries them, once.

    They leave the options on the way out: a credential that stayed in there
    would be passed on by every decorator, logged by anything that logs the
    options, and sent again to wherever a redirect pointed.
    """
    basic, bearer = merged.pop("auth_basic", None), merged.pop("auth_bearer", None)
    if normalized.get("authorization"):
        return

    if basic:
        credential = b64encode(str(basic).encode()).decode()
        normalized["authorization"] = [f"Authorization: Basic {credential}"]
    elif bearer:
        normalized["authorization"] = [f"Authorization: Bearer {bearer}"]


def _resolved(
    merged: dict[str, object], url: str, default_options: Mapping[str, object]
) -> UrlParts:
    base_uri = merged.pop("base_uri", None)
    base = parse_url(base_uri) if isinstance(base_uri, str) else None
    # Both are typed `Mapping[str, QueryValue]` by `RequestOptions`; the
    # encoder is what refuses a parameter of any other shape.
    query = cast("Mapping[str, QueryValue]", merged.get("query") or {})
    query_defaults = cast("Mapping[str, QueryValue]", default_options.get("query") or {})

    return resolve_url(parse_url(url, query), base, query_defaults)


def _apply_numbers(merged: dict[str, object]) -> None:
    version = merged.get("http_version")
    merged["http_version"] = str(version) if version else None

    timeout = merged.get("timeout")
    seconds = _DEFAULT_TIMEOUT if timeout is None else _as_float(timeout, "timeout")
    merged["timeout"] = _UNLIMITED_TIMEOUT if seconds < 0 else seconds
    merged["max_duration"] = _as_float(merged.get("max_duration") or 0, "max_duration")
    merged["max_connect_duration"] = _as_float(
        merged.get("max_connect_duration") or 0,
        "max_connect_duration",
    )


def _as_float(value: object, option: str) -> float:
    if isinstance(value, int | float):
        return float(value)

    raise InvalidArgumentError(f'Option "{option}" must be a number, "{debug_type(value)}" given.')
