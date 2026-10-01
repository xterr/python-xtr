"""The random-jti enrichment stamps a unique identifier on each payload."""

from __future__ import annotations

from xtr_security_core.user.in_memory_user import InMemoryUser

from xtr_security_jwt.services.payload_enrichment.random_jti_enrichment import RandomJtiEnrichment
from xtr_security_jwt.services.payload_enrichment_interface import PayloadEnrichmentInterface


def test_it_implements_the_interface() -> None:
    assert PayloadEnrichmentInterface in RandomJtiEnrichment.__mro__


def test_it_stamps_a_unique_id() -> None:
    payload: dict[str, object] = {}
    RandomJtiEnrichment().enrich(InMemoryUser("ada"), payload)

    jti = payload["jti"]
    assert isinstance(jti, str)
    assert len(jti) == 32


def test_it_differs_each_time() -> None:
    first: dict[str, object] = {}
    second: dict[str, object] = {}
    RandomJtiEnrichment().enrich(InMemoryUser("ada"), first)
    RandomJtiEnrichment().enrich(InMemoryUser("ada"), second)

    assert first["jti"] != second["jti"]
