"""The DKIM signature every email is sent with."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final, final

from xtr_mime.crypto import DkimOptions

from xtr_mailer._error_text import shown
from xtr_mailer.exception import InvalidArgumentError

__all__ = ["DkimSignerConfig"]

_CANONICALIZATIONS: Final = ("simple", "relaxed")


@final
@dataclass(frozen=True, slots=True)
class DkimSignerConfig:
    """Signs every email with DKIM. Needs the ``dkim`` extra.

    The key is opened when the first email is signed, not when the application starts: pass it
    through ``env("...")``, and the console still runs without it.

    Attributes:
        key: The private key as PEM text, or ``file://`` and the path of a PEM file. Never
            shown.
        domain: The signing domain, the signature's ``d=`` tag.
        select: The selector the public key is published under, its ``s=`` tag.
        passphrase: The passphrase of an encrypted key; empty for one that is not. Never
            shown.
        header_canon: How headers are canonicalized, ``simple`` or ``relaxed``; ``None``
            keeps the signer's default.
        body_canon: How the body is canonicalized, the same way.
        headers_to_ignore: The names of the headers left out of the signature; ``None`` keeps
            the signer's default.
        body_show_length: Whether the signature says how many body octets it covers;
            ``None`` keeps the signer's default.
    """

    key: str = field(repr=False)
    domain: str
    select: str
    passphrase: str = field(default="", repr=False)
    header_canon: str | None = None
    body_canon: str | None = None
    headers_to_ignore: Sequence[str] | None = None
    body_show_length: bool | None = None

    def __post_init__(self) -> None:
        """Refuse an empty key, domain or selector, and an unknown canonicalization.

        Raises:
            InvalidArgumentError: A required option is empty, or a canonicalization is not
                ``simple`` or ``relaxed``.
        """
        # Compared, never tested for truth: an env() placeholder cannot be tested at build.
        for option, value in (("key", self.key), ("domain", self.domain), ("select", self.select)):
            if value == "":
                raise InvalidArgumentError(f'The DKIM "{option}" option cannot be empty.')
        for option, canon in (("header_canon", self.header_canon), ("body_canon", self.body_canon)):
            if canon is not None and canon not in _CANONICALIZATIONS:
                raise InvalidArgumentError(
                    f'The DKIM "{option}" option must be "simple" or "relaxed" '
                    f'(got "{shown(canon)}").'
                )

    def default_options(self) -> DkimOptions:
        """Return the options the signer uses for every email: those set here."""
        options = DkimOptions()
        if self.header_canon is not None:
            _ = options.header_canon(self.header_canon)
        if self.body_canon is not None:
            _ = options.body_canon(self.body_canon)
        if self.headers_to_ignore is not None:
            _ = options.headers_to_ignore(self.headers_to_ignore)
        if self.body_show_length is not None:
            _ = options.body_show_length(self.body_show_length)
        return options
