"""The enrichment interface is runtime-checkable against a conforming enrichment."""

from __future__ import annotations

from xtr_security_jwt.services.payload_enrichment.null_enrichment import NullEnrichment
from xtr_security_jwt.services.payload_enrichment_interface import PayloadEnrichmentInterface


def test_a_conforming_enrichment_satisfies_the_interface() -> None:
    assert isinstance(NullEnrichment(), PayloadEnrichmentInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), PayloadEnrichmentInterface)
