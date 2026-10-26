"""The xtr-dependency-injection bundle for xtr-notifier."""

from __future__ import annotations

from .admin_recipient_config import AdminRecipientConfig
from .notifier_bundle import (
    CHANNEL_TAG,
    CHATTER_TRANSPORT_FACTORY_TAG,
    TEXTER_TRANSPORT_FACTORY_TAG,
    NotifierBundle,
)
from .notifier_config import NotifierConfig

__all__ = [
    "CHANNEL_TAG",
    "CHATTER_TRANSPORT_FACTORY_TAG",
    "TEXTER_TRANSPORT_FACTORY_TAG",
    "AdminRecipientConfig",
    "NotifierBundle",
    "NotifierConfig",
]
