"""Signs a message with DKIM (RFC 6376, RFC 8301), so a receiver can tell it came from a domain."""

from __future__ import annotations

import copy
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Final, TypeVar, final

from xtr_mime._error_text import escaped
from xtr_mime.exception import InvalidArgumentError, LogicError, MimeRuntimeError
from xtr_mime.header import FoldedHeader, Headers
from xtr_mime.message import Message
from xtr_mime.part import TextPart

from .dkim_options import DkimOptions
from .signed_body import SignedBody

if TYPE_CHECKING:
    from collections.abc import Iterable

    from xtr_mime.header import HeaderInterface

__all__ = ["DkimSigner"]

_NO_EXTRA: Final = 'The "dkim" extra is required to use DKIM: uv add "xtr-mime[dkim]".'
_FILE_PREFIX: Final = "file://"
# RFC 6376 names a selector and a domain in DNS: dot-separated labels. An underscore, which
# some providers put in selectors, is accepted too.
_LABELS: Final = re.compile(r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*")
# A DKIM-Signature already there is left out too, as RFC 6376 advises: a later hop may add
# its own above it, and signing one would sign what the next signer changes.
_ALWAYS_IGNORED: Final = frozenset({"return-path", "x-transport", "dkim-signature"})
_T = TypeVar("_T")


@final
class DkimSigner:
    """Signs messages for one domain and selector, with one RSA key.

    :meth:`sign` renders the message, hands the bytes to dkimpy and returns a new message with
    the DKIM-Signature field dkimpy wrote, folded as it was signed, above every other header —
    a DKIM-Signature already there included (RFC 6376, 5.6) — and the body as it was signed,
    which renders the same bytes however often it is sent. The signature covers every header
    of the message but ``Return-Path``, ``X-Transport``, an existing ``DKIM-Signature``, those
    the options name to ignore (never ``From``) and those without a body; it does not cover
    the body part's own headers (Content-Type and the like) beyond what the body hash holds.
    ``From`` is listed once more than it appears, so a From added above the signed one breaks
    the signature rather than being shown as its author.
    ``Bcc`` is neither sent nor signed, but the message returned keeps it, so the envelope read
    from that message still reaches every hidden recipient.

    The signature's ``t=`` tag is read by dkimpy from the system clock — the one time xtr-mime
    reads outside :mod:`xtr_clock`. Needs the ``dkim`` extra (``xtr-mime[dkim]``: dkimpy, and
    cryptography to open the key).
    """

    CANON_SIMPLE: ClassVar[str] = "simple"
    CANON_RELAXED: ClassVar[str] = "relaxed"
    ALGO_SHA256: ClassVar[str] = "rsa-sha256"
    ALGO_ED25519: ClassVar[str] = "ed25519-sha256"  # RFC 8463

    __slots__ = ("_default_options", "_domain_name", "_private_key", "_selector")

    def __init__(
        self,
        private_key: str | os.PathLike[str],
        domain_name: str,
        selector: str,
        *,
        default_options: DkimOptions | None = None,
        passphrase: str = "",
    ) -> None:
        """Open the key now, so a key that does not work fails here rather than at sending.

        Args:
            private_key: The key as PEM text, or the path to a PEM file — a path object, or a
                string starting with ``file://``.
            domain_name: The signing domain, the ``d=`` tag.
            selector: The selector the public key is published under, the ``s=`` tag.
            default_options: The options :meth:`sign` uses for whatever it is not given.
            passphrase: The passphrase of an encrypted key; empty for one that is not — a
                passphrase given for a key that is not encrypted is refused.

        Raises:
            LogicError: The ``dkim`` extra is not installed.
            InvalidArgumentError: The domain name or selector is not DNS labels, the key file
                cannot be read or its path is not one the file system accepts, or the key does
                not open or is not an RSA key of at least 1024 bits.
        """
        try:
            from ._dkimpy import load_private_key  # noqa: PLC0415 -- the dkim extra is optional.
        except ImportError as error:
            raise LogicError(_NO_EXTRA) from error
        _check_labels("domain name", domain_name)
        _check_labels("selector", selector)
        self._private_key: bytes = load_private_key(_read_key(private_key), passphrase)
        self._domain_name: str = domain_name
        self._selector: str = selector
        self._default_options: DkimOptions = default_options or DkimOptions()

    def sign(self, message: Message, options: DkimOptions | None = None) -> Message:
        """Return a message with the headers ``message`` is sent with, its Bcc and a DKIM-Signature.

        ``message`` is left as it is; the message returned carries its body as signed — a
        stream body is read here, once. ``options`` win over the signer's for each option
        they set.

        Raises:
            InvalidArgumentError: The algorithm or a canonicalization is not one DKIM knows,
                or a header to sign has a ``;`` in its name.
            MimeRuntimeError: The algorithm is ``ed25519-sha256``, which is not supported, or
                dkimpy refuses to sign: the message has no From to sign.
            LogicError: As rendering the message does — no author, no body to build.
            RfcComplianceError: As rendering the message does.
        """
        # The dkim extra is optional; building the signer loaded it.
        from ._dkimpy import SignatureRequest, sign  # noqa: PLC0415 -- see above.

        settings = self._settings(options or DkimOptions())
        headers = message.get_prepared_headers()
        body = message.get_body()
        if body is None:
            # What the message renders with when it has no body.
            body = TextPart("")
        names = _signed_names(
            header.get_name() for header in headers.all() if settings.signs(header)
        )
        rendered = b"".join(Message(headers, body).to_iterable())
        field = sign(
            rendered,
            SignatureRequest(
                selector=self._selector,
                domain_name=self._domain_name,
                private_key=self._private_key,
                canonicalization=settings.canonicalization,
                header_names=tuple(names),
                show_body_length=settings.show_body_length,
            ),
        )
        # With simple header canonicalization a verifier hashes the field byte for byte as
        # dkimpy folded it: refolded by the engine, it would no longer verify.
        signed = Headers(FoldedHeader(field), *headers.all())
        bcc = message.get_headers().get("Bcc")
        if bcc is not None:
            # Rendering leaves Bcc out, so the bytes sent stay the bytes signed.
            _ = signed.add(copy.deepcopy(bcc))
        return Message(signed, SignedBody(body, rendered))

    def _settings(self, options: DkimOptions) -> _Settings:
        """Merge ``options`` over the signer's, then over the defaults, and check them."""
        defaults = self._default_options
        algorithm = _first(options.get_algorithm(), defaults.get_algorithm(), self.ALGO_SHA256)
        if algorithm not in {self.ALGO_SHA256, self.ALGO_ED25519}:
            raise InvalidArgumentError(f'Invalid DKIM signing algorithm "{escaped(algorithm)}".')
        canons = (
            _first(options.get_header_canon(), defaults.get_header_canon(), self.CANON_RELAXED),
            _first(options.get_body_canon(), defaults.get_body_canon(), self.CANON_RELAXED),
        )
        for canon in canons:
            if canon not in {self.CANON_SIMPLE, self.CANON_RELAXED}:
                raise InvalidArgumentError(f'Invalid DKIM canonicalization "{escaped(canon)}".')
        if algorithm == self.ALGO_ED25519:
            raise MimeRuntimeError(
                f'The "{self.ALGO_ED25519}" DKIM signing algorithm is not supported yet.'
            )
        ignored = _first(options.get_headers_to_ignore(), defaults.get_headers_to_ignore(), ())
        show_length = _first(
            options.get_body_show_length(), defaults.get_body_show_length(), fallback=False
        )
        names = (_ALWAYS_IGNORED | {name.lower() for name in ignored}) - {"from"}
        return _Settings(canons, names, show_length)


@dataclass(frozen=True, slots=True)
class _Settings:
    """The options one signature is made with, every one decided."""

    canonicalization: tuple[str, str]
    ignored: frozenset[str]
    show_body_length: bool

    def signs(self, header: HeaderInterface) -> bool:
        """Tell whether ``header`` is signed: not ignored, and with a body to write."""
        return header.get_name().lower() not in self.ignored and bool(header.get_body_as_string())


def _first(value: _T | None, default: _T | None, fallback: _T) -> _T:
    """Return the option set for this signature, else the signer's, else ``fallback``."""
    if value is not None:
        return value
    return fallback if default is None else default


def _signed_names(names: Iterable[str]) -> list[str]:
    """Return the ``h=`` list: ``names``, then From once more when it is among them.

    Raises:
        InvalidArgumentError: A name holds ``;``, which would end the ``h=`` tag.
    """
    signed = list(names)
    for name in signed:
        if ";" in name:
            raise InvalidArgumentError(
                f'The "{escaped(name)}" header cannot be signed with DKIM: a ";" in its name '
                "would end the list of headers signed."
            )
    # Without a From, dkimpy refuses to sign: that error is the one to give.
    return [*signed, "From"] if any(name.lower() == "from" for name in signed) else signed


def _check_labels(what: str, value: str) -> None:
    if not _LABELS.fullmatch(value):
        raise InvalidArgumentError(
            f'The DKIM {what} "{escaped(value)}" is not dot-separated labels of letters, digits, '
            '"-" and "_".'
        )


def _read_key(private_key: str | os.PathLike[str]) -> bytes:
    """Return the PEM bytes of ``private_key``, read from its file when it names one."""
    if isinstance(private_key, str) and not private_key.startswith(_FILE_PREFIX):
        # A key is ASCII: anything else is replaced, and the key then fails to open.
        return private_key.encode("ascii", "replace")
    path = private_key.removeprefix(_FILE_PREFIX) if isinstance(private_key, str) else private_key
    try:
        return Path(path).read_bytes()
    except OSError as error:
        raise _unreadable(path, error.strerror) from error
    except ValueError as error:
        # A null byte, or text the file system cannot encode; UnicodeEncodeError's own text
        # quotes the path unescaped.
        raise _unreadable(path, "the path is not one the file system accepts") from error


def _unreadable(path: str | os.PathLike[str], reason: str | None) -> InvalidArgumentError:
    return InvalidArgumentError(
        f'Unable to load DKIM private key: the file "{escaped(os.fspath(path))}" cannot be '
        f"read: {reason}."
    )
