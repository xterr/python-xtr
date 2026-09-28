from __future__ import annotations

from xtr_logging.processor.processor_declaration import ProcessorDeclaration
from xtr_logging.processor.processors_declared_on import (
    PROCESSORS_ATTRIBUTE,
    processors_declared_on,
)


def test_it_reads_the_declarations_recorded_on_an_object() -> None:
    def target() -> None: ...

    setattr(target, PROCESSORS_ATTRIBUTE, (ProcessorDeclaration(channel="app"),))

    assert tuple(processors_declared_on(target)) == (ProcessorDeclaration(channel="app"),)


def test_an_object_without_declarations_has_none() -> None:
    assert tuple(processors_declared_on(object())) == ()


def test_anything_else_under_the_attribute_is_ignored() -> None:
    def target() -> None: ...

    setattr(target, PROCESSORS_ATTRIBUTE, ("not a declaration",))

    assert tuple(processors_declared_on(target)) == ()
