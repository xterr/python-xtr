"""The mailer bundle and its configuration.

Needs xtr-dependency-injection, which an application installs to list the bundle.
"""

from __future__ import annotations

from .dkim_signer_config import DkimSignerConfig
from .envelope_config import EnvelopeConfig
from .mailer_bundle import MAILER_TRANSPORT_FACTORY_TAG, MailerBundle
from .mailer_config import MailerConfig
from .smime_encrypter_config import SmimeEncrypterConfig
from .smime_signer_config import SmimeSignerConfig
from .tracking_config import TrackingConfig
from .transport_config import TransportConfig

__all__ = [
    "MAILER_TRANSPORT_FACTORY_TAG",
    "DkimSignerConfig",
    "EnvelopeConfig",
    "MailerBundle",
    "MailerConfig",
    "SmimeEncrypterConfig",
    "SmimeSignerConfig",
    "TrackingConfig",
    "TransportConfig",
]
