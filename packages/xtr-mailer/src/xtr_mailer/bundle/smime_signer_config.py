"""The S/MIME signature every email is sent with."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import final

from xtr_mailer.exception import InvalidArgumentError

__all__ = ["SmimeSignerConfig"]


@final
@dataclass(frozen=True, slots=True)
class SmimeSignerConfig:
    """Signs every email with S/MIME. Needs the ``smime`` extra.

    The certificate and the key are read when the first email is signed, not when the
    application starts.

    Attributes:
        certificate: The path of the signing certificate's PEM file.
        key: The path of the PEM file of the certificate's private key.
        passphrase: The passphrase of an encrypted key; empty for one that is not. Never
            shown.
        extra_certificates: The path of a PEM file of the intermediate certificates a receiver
            needs to follow the signing certificate up to one it trusts; ``None`` for none.
    """

    certificate: str
    key: str
    passphrase: str = field(default="", repr=False)
    extra_certificates: str | None = None

    def __post_init__(self) -> None:
        """Refuse an empty certificate or key path.

        Raises:
            InvalidArgumentError: The certificate or the key path is empty.
        """
        # Compared, never tested for truth: an env() placeholder cannot be tested at build.
        for option, value in (("certificate", self.certificate), ("key", self.key)):
            if value == "":
                raise InvalidArgumentError(f'The S/MIME signer "{option}" option cannot be empty.')
