"""The null enrichment adds nothing to a payload."""

from __future__ import annotations

from xtr_security_core.user.in_memory_user import InMemoryUser

from xtr_security_jwt.services.payload_enrichment.null_enrichment import NullEnrichment
from xtr_security_jwt.services.payload_enrichment_interface import PayloadEnrichmentInterface


def test_it_implements_the_interface() -> None:
    assert PayloadEnrichmentInterface in NullEnrichment.__mro__


def test_it_adds_nothing() -> None:
    payload: dict[str, object] = {"sub": "ada"}
    NullEnrichment().enrich(InMemoryUser("ada"), payload)

    assert payload == {"sub": "ada"}
