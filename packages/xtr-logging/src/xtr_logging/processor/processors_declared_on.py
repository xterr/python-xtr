"""Reading the ``@as_processor`` declarations recorded on a class or a function."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from .processor_declaration import ProcessorDeclaration

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["PROCESSORS_ATTRIBUTE", "processors_declared_on"]

PROCESSORS_ATTRIBUTE = "__xtr_logging_processors__"
"""Where :func:`~xtr_logging.decorator.as_processor` records declarations on a class or function."""


def processors_declared_on(obj: object) -> Iterable[ProcessorDeclaration]:
    """Yield every :func:`~xtr_logging.decorator.as_processor` declaration on ``obj``.

    A reader for
    :meth:`~xtr_dependency_injection.builder.ContainerBuilder.register_attribute_for_autoconfiguration`:
    the logging bundle uses it so a class decorated with ``@as_processor``
    becomes a service, and a decorated function is attached as it is, to
    every logger the kernel builds.
    """
    declarations: object = getattr(obj, PROCESSORS_ATTRIBUTE, ())
    if not isinstance(declarations, tuple):
        return ()
    typed = cast("tuple[object, ...]", declarations)
    return tuple(entry for entry in typed if isinstance(entry, ProcessorDeclaration))
