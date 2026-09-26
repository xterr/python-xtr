"""Declaring an analyzer where it is written: ``@as_analyzer("name")``.

The decorator only records a marker on the class. It imports nothing from a container:
the bundle reads the marker back with :func:`analyzers_declared_on`, handed to
``builder.register_attribute_for_autoconfiguration``. That is the whole pattern for a
library that wants its own decorator to mean something inside a kernel — the same one the
console, messenger and logging bundles use for ``@as_command``, ``@as_message_handler`` and
``@as_processor``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

__all__ = ["ANALYZER_ATTRIBUTE", "AnalyzerDeclaration", "analyzers_declared_on", "as_analyzer"]

ANALYZER_ATTRIBUTE: Final = "__fulltext_analyzer__"
"""Where ``@as_analyzer`` records its declaration on the class."""

A = TypeVar("A", bound=type)


@dataclass(frozen=True, slots=True)
class AnalyzerDeclaration:
    """What one ``@as_analyzer`` records.

    Attributes:
        name: The name a pipeline refers to the analyzer by.
    """

    name: str


def as_analyzer(name: str, /) -> Callable[[A], A]:
    """Declare the decorated class as the analyzer ``name``.

    The class must be buildable by a container: its constructor may ask for anything the
    container provides, including the library's own config.
    """

    def declare(target: A) -> A:
        setattr(target, ANALYZER_ATTRIBUTE, AnalyzerDeclaration(name))
        return target

    return declare


def analyzers_declared_on(obj: object) -> Iterable[AnalyzerDeclaration]:
    """Return the declaration ``@as_analyzer`` put on ``obj`` itself, if any.

    Read off the class's own namespace, so a subclass of an analyzer is not one by accident.
    """
    if not isinstance(obj, type):
        return ()
    declaration: object = vars(obj).get(ANALYZER_ATTRIBUTE)
    return (declaration,) if isinstance(declaration, AnalyzerDeclaration) else ()
