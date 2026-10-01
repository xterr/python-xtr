"""The chain enrichment runs each enrichment in turn against one payload."""

from __future__ import annotations

from xtr_security_core.user.in_memory_user import InMemoryUser

from xtr_security_jwt.services.payload_enrichment.chain_enrichment import ChainEnrichment
from xtr_security_jwt.services.payload_enrichment.null_enrichment import NullEnrichment
from xtr_security_jwt.services.payload_enrichment.random_jti_enrichment import RandomJtiEnrichment
from xtr_security_jwt.services.payload_enrichment_interface import PayloadEnrichmentInterface


def test_it_implements_the_interface() -> None:
    assert PayloadEnrichmentInterface in ChainEnrichment.__mro__


def test_it_runs_each_enrichment_in_turn() -> None:
    payload: dict[str, object] = {}
    ChainEnrichment([RandomJtiEnrichment(), NullEnrichment()]).enrich(InMemoryUser("ada"), payload)

    assert "jti" in payload


def test_an_empty_chain_adds_nothing() -> None:
    payload: dict[str, object] = {"sub": "ada"}
    ChainEnrichment([]).enrich(InMemoryUser("ada"), payload)

    assert payload == {"sub": "ada"}
