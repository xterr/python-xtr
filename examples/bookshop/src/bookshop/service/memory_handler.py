"""The handler the logging config names by id: ``ServiceHandlerConfig(id="memory")``.

A ``ServiceHandlerConfig(id=...)``, a ``ServiceProcessorConfig(id=...)``, a handler's string
``formatter`` and a fingers-crossed ``activation_strategy`` each name a service the
application registers under the matching interface, *qualified by that id*:

========================================  =================================  ====================
Config entry                              Registered as                      Id
========================================  =================================  ====================
``ServiceHandlerConfig(id="memory")``     ``(HandlerInterface, "memory")``   factory, qualified
``formatter="audit_json"``                ``(FormatterInterface, ...)``      factory, qualified
``activation_strategy="security"``        ``(ActivationStrategyInterface…)`` factory, qualified
``ServiceProcessorConfig(id="request")``  ``(ProcessorInterface, ...)``      class + ``@as_alias``
========================================  =================================  ====================

A missing id fails the build — the logging bundle checks every one in its ``process`` hook.
"""

from __future__ import annotations

from xtr_dependency_injection import as_service
from xtr_logging import HandlerInterface, TestHandler

__all__ = ["memory_handler"]


@as_service(qualifier="memory")
def memory_handler() -> HandlerInterface:
    """Keep the last records in memory — ``bookshop logs:recent`` prints them."""
    return TestHandler()
