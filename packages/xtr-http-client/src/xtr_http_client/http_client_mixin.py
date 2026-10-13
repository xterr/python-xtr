"""The work every client here does before a connection is opened."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Self

from typing_extensions import Unpack
from xtr_http_client_contracts import OPTIONS_DEFAULTS

from xtr_http_client.internal.body import json_encode, normalize_body
from xtr_http_client.internal.headers import normalize_headers, should_buffer
from xtr_http_client.internal.option_merge import merge_default_options
from xtr_http_client.internal.peer_fingerprint import normalize_peer_fingerprint
from xtr_http_client.internal.proxy import get_proxy
from xtr_http_client.internal.query import merge_query_string
from xtr_http_client.internal.request_preparation import prepare_request
from xtr_http_client.internal.url import parse_url, remove_dot_segments, resolve_url

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, Iterable, Mapping, Sequence

    from xtr_http_client_contracts import QueryValue, RequestOptions

    from xtr_http_client.proxy_config import ProxyConfig
    from xtr_http_client.url_parts import UrlParts

__all__ = ["HttpClientMixin"]


class HttpClientMixin:
    """What a client does to a request before it can be sent.

    Mixed into every client here, so all of them refuse the same requests,
    resolve the same URLs and send the same headers — which is what lets one
    be swapped for another without a caller noticing. A client is then only
    the part that opens connections.

    Its own state is the one thing a client needs from it: the options every
    request starts from. ``__init__`` takes them so a subclass can hand over
    what it was built with and get back the merged, normalised defaults the
    preparation steps expect.

    The steps are exposed as they are because a client uses them one at a
    time: a redirect needs :meth:`resolve_url` without the rest,
    :meth:`should_buffer` is asked once the response head arrives, and
    :meth:`get_proxy` is asked per connection rather than per request.
    """

    __slots__: tuple[str, ...] = ("_default_options",)

    _default_options: dict[str, object]

    def __init__(self, default_options: RequestOptions | None = None) -> None:
        """Start from the contract's defaults, with ``default_options`` over them."""
        self._default_options = dict(OPTIONS_DEFAULTS)
        if default_options:
            _, self._default_options = self.prepare_request(
                None,
                None,
                default_options,
                self._default_options,
            )

    def with_options(self, **options: Unpack[RequestOptions]) -> Self:
        """A copy of this client whose defaults have ``options`` over them.

        A copy rather than a change, so a caller can narrow a client for one
        job — a header, a timeout, a base URI — without the client everyone
        else holds changing under them.

        Raises:
            InvalidArgumentError: When an option is not one this client knows.
        """
        clone = copy.copy(self)
        # The clone is this very class, and its defaults are the one thing
        # about it that has to change; there is no other way to seed them.
        clone._default_options = self.merge_default_options(  # noqa: SLF001 — same class
            options,
            self._default_options,
        )

        return clone

    @classmethod
    def prepare_request(
        cls,
        method: str | None,
        url: str | None,
        options: Mapping[str, object],
        default_options: Mapping[str, object] | None = None,
        *,
        allow_extra_options: bool = False,
    ) -> tuple[UrlParts | None, dict[str, object]]:
        """Validate a request, merge it with the defaults, and resolve its URL.

        See :func:`xtr_http_client.internal.request_preparation.prepare_request`.
        """
        return prepare_request(
            cls.__qualname__,
            method,
            url,
            options,
            default_options,
            allow_extra_options=allow_extra_options,
        )

    @classmethod
    def merge_default_options(
        cls,
        options: Mapping[str, object],
        default_options: Mapping[str, object],
        *,
        allow_extra_options: bool = False,
    ) -> dict[str, object]:
        """Merge what a request asked for over what the client always asks for.

        See :func:`xtr_http_client.internal.option_merge.merge_default_options`.
        """
        return merge_default_options(
            cls.__qualname__,
            options,
            default_options,
            allow_extra_options=allow_extra_options,
        )

    @staticmethod
    def normalize_headers(
        headers: Mapping[str, str | Sequence[str]] | Sequence[str],
    ) -> dict[str, list[str]]:
        """Turn whatever a caller wrote into lines, keyed by the lowered name.

        See :func:`xtr_http_client.internal.headers.normalize_headers`.
        """
        return normalize_headers(headers)

    @staticmethod
    def normalize_body(
        body: object,
        normalized_headers: dict[str, list[str]] | None = None,
    ) -> bytes | Iterable[bytes] | AsyncIterable[bytes]:
        """Turn a body into bytes, or leave it as the stream of bytes it is.

        See :func:`xtr_http_client.internal.body.normalize_body`.
        """
        return normalize_body(body, normalized_headers)

    @staticmethod
    def json_encode(value: object) -> bytes:
        """Encode a value as the JSON body of a request.

        See :func:`xtr_http_client.internal.body.json_encode`.
        """
        return json_encode(value)

    @staticmethod
    def parse_url(url: str, query: Mapping[str, QueryValue] | None = None) -> UrlParts:
        """Read a URL apart, fixing its spelling on the way.

        See :func:`xtr_http_client.internal.url.parse_url`.
        """
        return parse_url(url, query)

    @staticmethod
    def resolve_url(
        url: UrlParts,
        base: UrlParts | None,
        query_defaults: Mapping[str, QueryValue] | None = None,
    ) -> UrlParts:
        """Resolve a URL against a base one.

        See :func:`xtr_http_client.internal.url.resolve_url`.
        """
        return resolve_url(url, base, query_defaults)

    @staticmethod
    def remove_dot_segments(path: str) -> str:
        """Take the ``.`` and ``..`` segments out of a path.

        See :func:`xtr_http_client.internal.url.remove_dot_segments`.
        """
        return remove_dot_segments(path)

    @staticmethod
    def merge_query_string(
        query_string: str | None,
        query_array: Mapping[str, QueryValue],
        *,
        replace: bool,
    ) -> str | None:
        """Merge parameters into the query string a URL already carries.

        See :func:`xtr_http_client.internal.query.merge_query_string`.
        """
        return merge_query_string(query_string, query_array, replace=replace)

    @staticmethod
    def normalize_peer_fingerprint(fingerprint: object) -> dict[str, str | tuple[str, ...]]:
        """Read a fingerprint into digests keyed by the algorithm that made them.

        See :func:`xtr_http_client.internal.peer_fingerprint.normalize_peer_fingerprint`.
        """
        return normalize_peer_fingerprint(fingerprint)

    @staticmethod
    def get_proxy(proxy: str | None, url: UrlParts, no_proxy: str | None) -> ProxyConfig | None:
        """Work out what a request should go through, if anything.

        See :func:`xtr_http_client.internal.proxy.get_proxy`.
        """
        return get_proxy(proxy, url, no_proxy)

    @staticmethod
    def should_buffer(headers: Mapping[str, Sequence[str]]) -> bool:
        """Tell whether a response of this kind is worth keeping once read.

        See :func:`xtr_http_client.internal.headers.should_buffer`.
        """
        return should_buffer(headers)
