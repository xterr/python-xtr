"""Listeners the mailer ships, each listening to the message event at its ``PRIORITY``.

The S/MIME encrypting listener finds each recipient's certificate through a
:class:`SmimeCertificateRepositoryInterface`.
"""

from __future__ import annotations

from .dkim_signed_message_listener import DkimSignedMessageListener
from .envelope_listener import EnvelopeListener
from .in_memory_smime_certificate_repository import InMemorySmimeCertificateRepository
from .message_listener import MessageListener
from .message_logger_listener import MessageLoggerListener
from .messenger_transport_listener import MessengerTransportListener
from .smime_certificate_repository_interface import SmimeCertificateRepositoryInterface
from .smime_encrypted_message_listener import SmimeEncryptedMessageListener
from .smime_signed_message_listener import SmimeSignedMessageListener

__all__ = [
    "DkimSignedMessageListener",
    "EnvelopeListener",
    "InMemorySmimeCertificateRepository",
    "MessageListener",
    "MessageLoggerListener",
    "MessengerTransportListener",
    "SmimeCertificateRepositoryInterface",
    "SmimeEncryptedMessageListener",
    "SmimeSignedMessageListener",
]
