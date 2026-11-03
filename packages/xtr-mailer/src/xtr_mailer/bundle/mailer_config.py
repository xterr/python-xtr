"""The one configuration an application writes to send email."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final, cast, final

from xtr_mailer._error_text import shown
from xtr_mailer.exception import InvalidArgumentError

from .dkim_signer_config import DkimSignerConfig
from .envelope_config import EnvelopeConfig
from .smime_encrypter_config import SmimeEncrypterConfig
from .smime_signer_config import SmimeSignerConfig
from .tracking_config import TrackingConfig
from .transport_config import TransportConfig

__all__ = ["MailerConfig"]

#: The transport of an application configuring none: it discards every email.
_DISCARDING: Final = {"main": TransportConfig("null://null")}


def _no_transports() -> dict[str, str | TransportConfig]:
    """The empty set of named transports a zero-config application starts with."""
    return {}


def _no_headers() -> dict[str, str | Sequence[str]]:
    """The empty set of default headers a zero-config application starts with."""
    return {}


@final
@dataclass(frozen=True, slots=True)
class MailerConfig:
    """Values the bundle builds the mailer, its transports and its listeners from.

    Buildable with no arguments: the zero-config mailer sends through ``null://null``, which
    discards every email, so it builds, boots and sends with nothing configured.

    Attributes:
        dsn: The one transport, named ``main``: a DSN, or a ``failover(...)`` /
            ``roundrobin(...)`` group of them. It carries credentials, so pass it through
            ``env("MAILER_DSN")``; it is never shown, and read when the first email is sent.
        transports: Named transports instead, each a DSN or a :class:`TransportConfig`; an
            email goes through the first unless its ``X-Transport`` header names another.
        envelope: The sender and recipients every email is delivered for.
        headers: Headers every email gets, by name — a value, or several for an address list.
        tracking: Whether a provider tracks the opens and clicks of every email.
        dkim_signer: Signs every email with DKIM; ``None`` signs nothing.
        smime_signer: Signs every email with S/MIME; ``None`` signs nothing.
        smime_encrypter: Encrypts each email asking for it with S/MIME; ``None`` encrypts
            nothing.
        http_client: The qualifier of the HTTP client provider transports are reached through;
            ``None`` means the default one.
    """

    dsn: str | None = field(default=None, repr=False)
    transports: Mapping[str, str | TransportConfig] = field(
        default_factory=_no_transports, repr=False
    )
    envelope: EnvelopeConfig = field(default_factory=EnvelopeConfig)
    headers: Mapping[str, str | Sequence[str]] = field(default_factory=_no_headers)
    tracking: TrackingConfig = field(default_factory=TrackingConfig)
    dkim_signer: DkimSignerConfig | None = None
    smime_signer: SmimeSignerConfig | None = None
    smime_encrypter: SmimeEncrypterConfig | None = None
    http_client: str | None = None

    def __post_init__(self) -> None:
        """Refuse a DSN beside named transports, and a transport or header of the wrong shape.

        No DSN is read here: it is read when the first email is sent, so one given through
        ``env()`` is checked where it is used. No error quotes one.

        Raises:
            InvalidArgumentError: ``dsn`` and ``transports`` are both given, the DSN is not a
                string or is empty, a transport is neither a DSN nor a
                :class:`TransportConfig`, a name or a DSN is empty, or a header value is
                neither text nor a list of text.
        """
        # Each is read as an application may have written it, whatever the annotations promise.
        if self.dsn is not None:
            if self.transports:
                raise InvalidArgumentError('"dsn" and "transports" cannot be used together.')
            _check_dsn(self.dsn)
        _check_transports(self.transports)
        _check_headers(self.headers)

    def get_transports(self) -> dict[str, TransportConfig]:
        """Return every transport by name, in order: ``main`` alone for a single DSN."""
        if self.dsn is not None:
            return {"main": TransportConfig(self.dsn)}
        if not self.transports:
            return dict(_DISCARDING)
        return {
            name: transport
            if isinstance(transport, TransportConfig)
            else TransportConfig(transport)
            for name, transport in self.transports.items()
        }


def _check_dsn(dsn: object) -> None:
    """Refuse a DSN that is not a string, or is empty — without quoting it.

    Raises:
        InvalidArgumentError: ``dsn`` is not a string, or is empty.
    """
    if not isinstance(dsn, str):
        raise InvalidArgumentError('The "dsn" option must be a string.')
    # Compared, never tested for truth: an env() placeholder cannot be tested at build.
    if dsn == "":
        raise InvalidArgumentError('The "dsn" option cannot be empty.')


def _check_transports(transports: Mapping[str, object]) -> None:
    """Refuse an empty name, and a transport that is no DSN, or an empty one.

    Raises:
        InvalidArgumentError: A name is empty, or a transport is neither a DSN nor a
            :class:`TransportConfig`, or its DSN is empty.
    """
    for name, transport in transports.items():
        if name == "":
            raise InvalidArgumentError("A transport name cannot be empty.")
        if not isinstance(transport, str | TransportConfig):
            raise InvalidArgumentError(
                f'The "{shown(name)}" transport must be a DSN or a TransportConfig.'
            )
        if transport == "":
            raise InvalidArgumentError(f'The "{shown(name)}" transport\'s DSN cannot be empty.')


def _check_headers(headers: Mapping[str, object]) -> None:
    """Refuse a header value that is neither text nor a list of text.

    Raises:
        InvalidArgumentError: A value is of another kind.
    """
    for name, value in headers.items():
        if not (isinstance(value, str) or _is_text_list(value)):
            raise InvalidArgumentError(
                f'The "{shown(name)}" header must be a string or a list of strings.'
            )


def _is_text_list(value: object) -> bool:
    """Tell whether ``value`` is a list or a tuple of strings."""
    if not isinstance(value, list | tuple):
        return False
    items = cast("Sequence[object]", value)
    return all(isinstance(item, str) for item in items)
