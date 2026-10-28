"""Events received from another system, handed to the consumer registered under their name.

An event from elsewhere — a delivery report, a payment notice, a message from a provider — is
one value type here: the name of where it came from, an id, and the payload as it arrived. A
consumer is registered under that name, and the event reaches it directly or through a message
bus. A mail provider's reports have types of their own derived from it, carrying as fields the
facts every provider reports.
"""

from __future__ import annotations

from .consumer import ConsumerInterface, ConsumerLocator
from .decorator import as_remote_event_consumer
from .event import AbstractMailerEvent, MailerDeliveryEvent, MailerEngagementEvent
from .payload_converter_interface import PayloadConverterInterface
from .remote_event import RemoteEvent

__all__ = [
    "AbstractMailerEvent",
    "ConsumerInterface",
    "ConsumerLocator",
    "MailerDeliveryEvent",
    "MailerEngagementEvent",
    "PayloadConverterInterface",
    "RemoteEvent",
    "as_remote_event_consumer",
]
