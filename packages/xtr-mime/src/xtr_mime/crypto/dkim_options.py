"""The options a DKIM signature is made with, set one by one."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Self

__all__ = ["DkimOptions"]


@final
class DkimOptions:
    """Options for :class:`~xtr_mime.crypto.DkimSigner`, each set by a method of its name.

    An option left unset is ``None`` here and takes the signer's value: the options a signer
    was built with, else its defaults — ``rsa-sha256``, ``relaxed`` header and body
    canonicalization, no body length shown, no header ignored beyond those always left out.
    """

    __slots__ = (
        "_algorithm",
        "_body_canon",
        "_body_show_length",
        "_header_canon",
        "_headers_to_ignore",
    )

    def __init__(self) -> None:
        """Start with no option set."""
        self._algorithm: str | None = None
        self._body_show_length: bool | None = None
        self._header_canon: str | None = None
        self._body_canon: str | None = None
        self._headers_to_ignore: tuple[str, ...] | None = None

    def algorithm(self, algorithm: str) -> Self:
        """Set the signing algorithm: ``DkimSigner.ALGO_SHA256``, the one supported."""
        self._algorithm = algorithm
        return self

    def body_show_length(self, show: bool) -> Self:
        """Set whether the signature says how many body octets it covers (its ``l=`` tag)."""
        self._body_show_length = show
        return self

    def header_canon(self, canon: str) -> Self:
        """Set how headers are canonicalized: ``simple`` or ``relaxed``."""
        self._header_canon = canon
        return self

    def body_canon(self, canon: str) -> Self:
        """Set how the body is canonicalized: ``simple`` or ``relaxed``."""
        self._body_canon = canon
        return self

    def headers_to_ignore(self, headers: Iterable[str]) -> Self:
        """Set the names of the headers left out of the signature, whatever their case.

        ``From`` is signed even when named here: a signature must cover it.
        """
        self._headers_to_ignore = tuple(headers)
        return self

    def get_algorithm(self) -> str | None:
        """Return the signing algorithm, ``None`` unless set."""
        return self._algorithm

    def get_body_show_length(self) -> bool | None:
        """Return whether the body length is shown, ``None`` unless set."""
        return self._body_show_length

    def get_header_canon(self) -> str | None:
        """Return the header canonicalization, ``None`` unless set."""
        return self._header_canon

    def get_body_canon(self) -> str | None:
        """Return the body canonicalization, ``None`` unless set."""
        return self._body_canon

    def get_headers_to_ignore(self) -> tuple[str, ...] | None:
        """Return the names of the headers left out, ``None`` unless set."""
        return self._headers_to_ignore
