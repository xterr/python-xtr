from __future__ import annotations

import inspect
from typing import Annotated

from xtr_dependency_injection import Reference, Target

from xtr_mailer.bundle._crypto_listeners import smime_encrypted_message_listener
from xtr_mailer.event_listener import InMemorySmimeCertificateRepository


def _repository_annotation(reference: Reference) -> object:
    factory = smime_encrypted_message_listener(reference)
    annotations: dict[str, object] = inspect.get_annotations(factory)
    return annotations["repository"]


def test_an_unqualified_repository_is_injected_by_its_type() -> None:
    annotation = _repository_annotation(Reference(InMemorySmimeCertificateRepository))

    assert annotation is InMemorySmimeCertificateRepository


def test_a_qualified_repository_is_injected_by_its_type_and_qualifier() -> None:
    annotation = _repository_annotation(Reference(InMemorySmimeCertificateRepository, "certs"))

    assert annotation == Annotated[InMemorySmimeCertificateRepository, Target("certs")]
