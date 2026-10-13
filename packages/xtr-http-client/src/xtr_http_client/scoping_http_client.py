"""The client that picks a request's defaults from the URL it is for."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import TYPE_CHECKING, cast, final
from urllib.parse import urljoin, urlsplit

from typing_extensions import Unpack, override
from xtr_http_client_contracts import HttpClientInterface
from xtr_http_message import Uri

from .exception import InvalidArgumentError
from .internal.option_merge import as_options

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Self

    from xtr_http_client_contracts import HttpResponseInterface, RequestOptions
    from xtr_http_message_contracts import RequestInterface

__all__ = ["ScopingHttpClient"]


@final
class ScopingHttpClient(HttpClientInterface):
    r"""Wraps a client and gives each request the options its URL falls under.

    One application talks to several services, and each wants its own
    credentials, headers and deadlines. Written at the call sites, that is the
    same four options repeated wherever a service is reached, and one place
    that forgot them. Here it is said once: a scope is a regular expression
    the start of a URL is matched against, and the options every request
    landing in it starts from.

    ```python
    client = ScopingHttpClient(
        inner,
        {r"https://api\.example\.com/": {"auth_bearer": "t0ken"}},
    )
    response = await client.request("GET", "https://api.example.com/orders")
    ```

    What the request itself asked for always wins — a scope fills in what was
    left out, it never overrides. ``headers`` is the one option merged rather
    than replaced, name by name, so a scope-wide ``Accept`` survives a request
    setting a ``Content-Type`` of its own.

    With a ``default_regexp``, that scope's ``base_uri`` also resolves a
    relative URL, which is what makes :meth:`for_base_uri` read as "this
    client is that service".
    """

    __slots__ = ("_by_regexp", "_client", "_default_regexp")

    def __init__(
        self,
        client: HttpClientInterface,
        default_options_by_regexp: Mapping[str, RequestOptions],
        default_regexp: str | None = None,
    ) -> None:
        """Scope ``client``, matching a URL against each regexp in turn.

        Args:
            client: The client every vetted request is handed to.
            default_options_by_regexp: Each scope's pattern mapped to the
                options a request falling in it starts from. The first
                pattern matching the start of a URL is the one that applies,
                so order them from the most specific to the least.
            default_regexp: Which of those scopes a relative URL belongs to,
                and whose ``base_uri`` resolves it. ``None`` leaves a
                relative URL to the wrapped client.

        Raises:
            InvalidArgumentError: When ``default_regexp`` names a scope that
                is not in ``default_options_by_regexp`` — a default scope
                with no options is a client whose relative URLs quietly
                resolve against nothing.
        """
        if default_regexp is not None and default_regexp not in default_options_by_regexp:
            raise InvalidArgumentError(
                f'No options are mapped to the provided "{default_regexp}" default regexp.'
            )

        self._client = client
        self._by_regexp = dict(default_options_by_regexp)
        self._default_regexp = default_regexp

    @classmethod
    def for_base_uri(
        cls,
        client: HttpClientInterface,
        base_uri: str,
        default_options: RequestOptions | None = None,
        regexp: str | None = None,
    ) -> Self:
        """Scope ``client`` to one service, reached at ``base_uri``.

        Args:
            client: The client every request is handed to.
            base_uri: What a relative URL resolves against, and — unless
                ``regexp`` says otherwise — what a URL must start with to be
                in scope.
            default_options: What a request in scope starts from.
            regexp: The scope's pattern, for a service whose URLs are not all
                under one base.

        Returns:
            A client scoped to that one base URI.
        """
        return cls._scoped(client, [base_uri], default_options, regexp)

    @classmethod
    def for_base_uris(
        cls,
        client: HttpClientInterface,
        base_uris: Sequence[str],
        default_options: RequestOptions | None = None,
        regexp: str | None = None,
    ) -> Self:
        """Scope ``client`` to one service reachable at several base URIs.

        The scope matches all of them, so the options keep applying whichever
        one a request is resolved against; the first is what a relative URL
        resolves against.

        Args:
            client: The client every request is handed to.
            base_uris: Where the service answers, the first being the default.
            default_options: What a request in scope starts from.
            regexp: The scope's pattern, replacing the one built from them.

        Returns:
            A client scoped to all of those base URIs.

        Raises:
            InvalidArgumentError: When no base URI is given, since a scope
                over nothing would match nothing and resolve nothing.
        """
        uris = list(base_uris)
        if not uris:
            raise InvalidArgumentError("At least one base URI must be provided.")

        return cls._scoped(client, uris, default_options, regexp)

    @override
    async def request(
        self,
        method: str,
        url: str,
        **options: Unpack[RequestOptions],
    ) -> HttpResponseInterface:
        """Make a request for ``method`` and ``url``, under the scope it falls in.

        Args:
            method: The HTTP method, in upper case.
            url: The URL to request, absolute or relative to a ``base_uri``.
            **options: How the request is to be made; the scope fills in what
                is left out.

        Returns:
            Whatever the wrapped client answers.

        Raises:
            InvalidArgumentError: For an invalid method, URL or option.
            TransportError: When no answer came.
        """
        target, scoped = self._scope(url, options)

        return await self._client.request(method, target, **scoped)

    @override
    async def send_request(
        self,
        request: RequestInterface,
        **options: Unpack[RequestOptions],
    ) -> HttpResponseInterface:
        """Send ``request`` under the scope the URI it carries falls in.

        Args:
            request: The request to send; it goes on carrying the URL this
                client resolved for it.
            **options: What the request leaves out; the scope fills in what
                both leave out.

        Returns:
            Whatever the wrapped client answers.

        Raises:
            InvalidArgumentError: For an invalid method, URL or option.
            TransportError: When no answer came.
        """
        target, scoped = self._scope(str(request.get_uri()), options)

        return await self._client.send_request(request.with_uri(Uri(target)), **scoped)

    @override
    def with_options(self, **options: Unpack[RequestOptions]) -> Self:
        """Return a copy around a wrapped client whose defaults have ``options`` over them.

        The scopes are kept as they are: they say what belongs to which
        service, which is not something a caller narrowing a client for one
        job is changing.

        Args:
            **options: The defaults of the wrapped client of the copy.

        Returns:
            A new client; this one is left as it was.

        Raises:
            InvalidArgumentError: When an option is invalid.
        """
        return type(self)(
            self._client.with_options(**options),
            self._by_regexp,
            self._default_regexp,
        )

    @classmethod
    def _scoped(
        cls,
        client: HttpClientInterface,
        base_uris: list[str],
        default_options: RequestOptions | None,
        regexp: str | None,
    ) -> Self:
        """One scope over ``base_uris``, which is also the default one."""
        pattern = regexp if regexp is not None else "|".join(_in_scope(uri) for uri in base_uris)
        options: Mapping[str, object] = {**(default_options or {}), "base_uri": base_uris[0]}

        return cls(client, {pattern: as_options(options)}, pattern)

    def _scope(
        self,
        url: str,
        options: Mapping[str, object],
    ) -> tuple[str, RequestOptions]:
        """The URL to request and the options to make it with, scope included."""
        given = dict(options)
        base = given.get("base_uri")

        if isinstance(base, str):
            url = urljoin(base, url)
            del given["base_uri"]
        elif not urlsplit(url).scheme and self._default_regexp is not None:
            default = self._by_regexp[self._default_regexp].get("base_uri")
            if isinstance(default, str):
                url = urljoin(default, url)

        for pattern, defaults in self._by_regexp.items():
            if re.match(pattern, url):
                given = _under(given, defaults)
                break

        return url, as_options(given)


def _in_scope(base_uri: str) -> str:
    """The pattern matching every URL under ``base_uri``, taken literally."""
    return re.escape(urljoin(base_uri, "."))


def _under(given: dict[str, object], defaults: Mapping[str, object]) -> dict[str, object]:
    """``defaults`` under ``given``: an option the request named is the one used."""
    merged = dict(given)
    for name, value in defaults.items():
        _ = merged.setdefault(name, value)

    headers = _headers(given.get("headers"))
    scoped = _headers(defaults.get("headers"))
    if headers is not None and scoped is not None:
        # Name by name rather than whole, so a request setting one header
        # still sends the scope's others; the request's come first, as they
        # are the ones that were asked for here.
        merged["headers"] = {**headers, **{n: v for n, v in scoped.items() if n not in headers}}

    return merged


def _headers(value: object) -> Mapping[str, object] | None:
    """``value`` as the ``headers`` option, or ``None`` when it is not one."""
    if isinstance(value, Mapping):
        return cast("Mapping[str, object]", value)

    return None
