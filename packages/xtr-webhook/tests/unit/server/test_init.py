from __future__ import annotations

from xtr_webhook import server

_EXPORTED = [
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


def test_every_exported_name_resolves() -> None:
    assert [name for name in server.__all__ if not hasattr(server, name)] == []


def test_it_exports_what_builds_an_outgoing_webhook() -> None:
    assert sorted(server.__all__) == _EXPORTED
