"""The sending side: what a webhook leaving this application is signed and shaped like.

A webhook is built by a chain of configurators, each writing one part of the same
:class:`OutgoingRequest` — the headers that name the event, the body the payload is
written into, the signature over both. They are separate because receivers disagree
about all three, so an application that has to satisfy an unusual one adds or replaces
a step rather than the sender.

The :class:`Transport` runs that chain and posts the result through an
:class:`HttpSenderInterface`, so everything here works — and is tested — with no HTTP
client installed; the client arrives with the bridge that wraps one.
"""

from __future__ import annotations

from .header_signature_configurator import HeaderSignatureConfigurator
from .headers_configurator import HeadersConfigurator
from .http_sender_interface import HttpSenderInterface
from .json_body_configurator import JsonBodyConfigurator
from .json_payload_serializer import JsonPayloadSerializer
from .outgoing_request import OutgoingRequest
from .payload_serializer_interface import PayloadSerializerInterface
from .request_configurator_interface import RequestConfiguratorInterface
from .signature_format import SignatureFormat
from .transport import Transport
from .transport_interface import TransportInterface

__all__ = [
    "HeaderSignatureConfigurator",
    "HeadersConfigurator",
    "HttpSenderInterface",
    "JsonBodyConfigurator",
    "JsonPayloadSerializer",
    "OutgoingRequest",
    "PayloadSerializerInterface",
    "RequestConfiguratorInterface",
    "SignatureFormat",
    "Transport",
    "TransportInterface",
]
