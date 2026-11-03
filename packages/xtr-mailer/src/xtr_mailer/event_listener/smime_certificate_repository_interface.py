"""Where the S/MIME certificate an email is encrypted for is found, by address."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["SmimeCertificateRepositoryInterface"]


@runtime_checkable
class SmimeCertificateRepositoryInterface(Protocol):
    """Finds the certificate of the person behind an email address.

    :class:`~xtr_mailer.event_listener.SmimeEncryptedMessageListener` asks it for each envelope
    recipient's certificate — the sender's too, when it encrypts for the sender.
    """

    def find_certificate_path_for(self, email: str) -> str | None:
        """Return the path of the PEM certificate of ``email``; ``None`` when there is none.

        ``email`` is a bare address, without a name.
        """
        ...
