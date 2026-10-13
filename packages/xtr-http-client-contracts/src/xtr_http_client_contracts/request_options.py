"""Everything a request can be asked to do, as one typed mapping."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias, TypedDict

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, Mapping, Sequence

__all__ = ["QueryValue", "RequestOptions"]

QueryValue: TypeAlias = (
    "str | int | float | bool | Sequence[QueryValue] | Mapping[str, QueryValue] | None"
)
"""What a query string parameter may hold, nested as deeply as it needs to be.

A scalar becomes one parameter, a sequence repeats the name, and a mapping
names sub-keys — so ``{"tag": ["new", "sale"]}`` and ``{"page": {"size": 10}}``
both have an unambiguous way of being written out. ``None`` drops the
parameter.
"""


class RequestOptions(TypedDict, total=False):
    """How a request is to be made, beyond its method and URL.

    Every option is optional, and an option left out is one nobody asked
    about: the client fills it in from its own defaults, which start at
    :data:`OPTIONS_DEFAULTS
    <xtr_http_client_contracts.options_defaults.OPTIONS_DEFAULTS>`. The same
    keys are what :meth:`HttpClientInterface.with_options
    <xtr_http_client_contracts.http_client_interface.HttpClientInterface.with_options>`
    takes, where they become the defaults of the client it returns.

    A name not listed here is refused. ``extra`` carries what one client
    understands and another has no use for, so entries in it may be ignored.

    Attributes:
        auth_basic: Credentials for basic authentication: ``"user:password"``,
            or the user alone, or the two as a tuple. ``None`` sends none.
        auth_bearer: A token to send as a bearer credential. ``None`` sends
            none.
        query: Parameters to merge into the URL's query string. They win over
            a parameter of the same name already in the URL.
        headers: Headers to send, a mapping of name to one value or several.
        body: What to send as the request body. Bytes or text go as they are;
            a mapping is sent as an HTML form; an async iterable of bytes is
            sent as it is produced, which is how a body too large to hold is
            uploaded.
        json: A value to send as a JSON body. The client encodes it and sets
            a JSON content type unless ``headers`` already names one. Setting
            both this and ``body`` is refused.
        user_data: Anything the caller wants to find again on the response,
            under the ``user_data`` entry of ``get_info()``. Never read by
            the client.
        max_redirects: How many redirects to follow. Zero or less follows
            none, which leaves the 3xx to be answered with.
        http_version: The HTTP version to ask for — ``"1.0"``, ``"1.1"``,
            ``"2"`` or ``"2.0"``. ``None`` leaves the client to use the best
            version the connection offers.
        base_uri: The URI a relative URL is resolved against. A sequence of
            them is only for a client that retries, which moves along it from
            one attempt to the next.
        timeout: How long the transfer may go quiet for, in seconds. ``None``
            is 60 seconds.
        max_duration: How long the whole request and response may take, in
            seconds. Zero is unlimited.
        max_connect_duration: How long resolving, connecting and the TLS
            handshake may take, in seconds. Zero is unlimited.
        resolve: Host to IP address, used instead of asking a resolver. This
            is what pins a request to an address that has already been
            checked, so that nothing can change under it between the check
            and the connection.
        proxy: The proxy to go through, as a URL.
        no_proxy: Hosts to reach directly, comma separated.
        verify_peer: Whether to check that the peer's certificate is trusted.
        verify_host: Whether to check that the certificate is for the host
            being asked for.
        cafile: A file of certificates to trust instead of the defaults.
        capath: A directory of certificates to trust instead of the defaults.
        local_cert: A client certificate to present.
        local_pk: The private key of ``local_cert``, when it is kept apart.
        passphrase: The passphrase of ``local_pk``.
        max_retries: How many times a client that retries may try the request
            again. A client that does not retry ignores it.
        extra: Additional options a client may ignore when it does not
            support them, unlike the regular options it must refuse:
            ``use_persistent_connections`` says whether to use persistent
            connections where supported, ``trace_content`` whether a tracing
            client keeps the bodies.
    """

    auth_basic: str | tuple[str] | tuple[str, str] | None
    auth_bearer: str | None
    query: Mapping[str, QueryValue]
    headers: Mapping[str, str | Sequence[str]]
    body: bytes | str | Mapping[str, object] | AsyncIterable[bytes]
    json: object
    user_data: object
    max_redirects: int
    http_version: str | None
    base_uri: str | Sequence[str] | None
    timeout: float | None
    max_duration: float
    max_connect_duration: float
    resolve: Mapping[str, str]
    proxy: str | None
    no_proxy: str | None
    verify_peer: bool
    verify_host: bool
    cafile: str | None
    capath: str | None
    local_cert: str | None
    local_pk: str | None
    passphrase: str | None
    max_retries: int
    extra: Mapping[str, object]
