"""Everything a request can be asked to do, as one typed mapping."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias, TypedDict

if TYPE_CHECKING:
    import ssl
    from collections.abc import AsyncIterable, Callable, Iterable, Mapping, Sequence

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

    A client need not support every option, and it must say so by raising
    :class:`TransportError
    <xtr_http_client_contracts.exception.transport_error.TransportError>`
    rather than ignoring what it cannot honour. ``extra`` is the exception:
    it carries what one client understands and another has no use for, so
    entries in it may be ignored.

    Attributes:
        auth_basic: Credentials for basic authentication: ``"user:password"``,
            or the user alone, or the two as a tuple. ``None`` sends none,
            which is what the default is for.
        auth_bearer: A token to send as a bearer credential. ``None`` sends
            none.
        query: Parameters to merge into the URL's query string. They win over
            a parameter of the same name already in the URL.
        headers: Headers to send. A mapping of name to one value or several,
            or a sequence of ``"Name: value"`` lines.
        body: What to send as the request body. Bytes or text go as they are;
            a mapping is sent as an HTML form; an iterable of bytes — async
            or not — is sent as it is produced, which is how a body too large
            to hold is uploaded.
        json: A value to send as a JSON body. The client encodes it and sets
            a JSON content type unless ``headers`` already names one. Setting
            both this and ``body`` is refused.
        user_data: Anything the caller wants to find again on the response,
            under the ``user_data`` entry of ``get_info()``. Never read by
            the client.
        max_redirects: How many redirects to follow. Zero or less follows
            none, which leaves the 3xx to be answered with. A hop that
            changes the scheme, the host or the port is not trusted with what
            was sent to the one before it, so ``Authorization``, ``Cookie``
            and ``Host`` are dropped when any of the three changes.
        http_version: The HTTP version to ask for — ``"1.0"``, ``"1.1"``,
            ``"2"`` or ``"2.0"``. ``None`` leaves the client to use the best
            version the connection offers.
        base_uri: The URI a relative URL is resolved against.
        buffer: Whether to keep the body once it has been read, so it can be
            read again. A callable decides from the response headers, which
            it is given keyed by lowercased name.
        on_progress: Called as the transfer goes on, with the bytes received
            so far, the total when it is known (zero when it is not), and the
            info as it stands. Raising from it aborts the request, which is
            how a caller cancels mid-transfer.
        resolve: Host to IP address, used instead of asking a resolver. This
            is what pins a request to an address that has already been
            checked, so that nothing can change under it between the check
            and the connection.
        proxy: The proxy to go through. ``None`` falls back to the proxy
            environment variables.
        no_proxy: Hosts to reach directly, comma separated.
        timeout: How long the transfer may go quiet for, in seconds. ``None``
            leaves the client to choose; the clients here settle on 60
            seconds.
        max_duration: How long the whole request and response may take, in
            seconds. Zero or less is unlimited.
        max_connect_duration: How long resolving, connecting and the TLS
            handshake may take, in seconds. Zero or less is unlimited.
        bindto: The local interface or socket to send from. ``"0"`` is any.
        verify_peer: Whether to check that the peer's certificate is trusted.
        verify_host: Whether to check that the certificate is for the host
            being asked for.
        cafile: A file of certificates to trust instead of the defaults.
        capath: A directory of certificates to trust instead of the defaults.
        local_cert: A client certificate to present.
        local_pk: The private key of ``local_cert``, when it is kept apart.
        passphrase: The passphrase of ``local_pk``.
        ciphers: The cipher suites to offer, in the usual list form.
        peer_fingerprint: Digests the peer's certificate must match, keyed by
            the algorithm that produced them.
        capture_peer_cert_chain: Whether to keep the peer's certificate chain
            under the ``peer_certificate_chain`` entry of ``get_info()``.
        crypto_method: The lowest TLS version to accept.
        extra: Options one client understands and another may ignore.
    """

    auth_basic: str | tuple[str] | tuple[str, str] | None
    auth_bearer: str | None
    query: Mapping[str, QueryValue]
    headers: Mapping[str, str | Sequence[str]] | Sequence[str]
    body: bytes | str | Mapping[str, object] | Iterable[bytes] | AsyncIterable[bytes]
    json: object
    user_data: object
    max_redirects: int
    http_version: str | None
    base_uri: str | None
    buffer: bool | Callable[[Mapping[str, Sequence[str]]], bool]
    on_progress: Callable[[int, int, Mapping[str, object]], None] | None
    resolve: Mapping[str, str]
    proxy: str | None
    no_proxy: str | None
    timeout: float | None
    max_duration: float
    max_connect_duration: float
    bindto: str
    verify_peer: bool
    verify_host: bool
    cafile: str | None
    capath: str | None
    local_cert: str | None
    local_pk: str | None
    passphrase: str | None
    ciphers: str | None
    peer_fingerprint: Mapping[str, str | Sequence[str]] | None
    capture_peer_cert_chain: bool
    crypto_method: ssl.TLSVersion
    extra: Mapping[str, object]
