"""A compiler pass: it sees, and may change, every definition.

``@compiler_pass`` goes on a class implementing ``CompilerPassInterface``; the kernel builds
it with no arguments. Passes run stage by stage — ``BEFORE_OPTIMIZATION``, ``OPTIMIZE``,
``BEFORE_REMOVING``, ``REMOVE``, ``AFTER_REMOVING`` — and within a stage by priority, highest
first: the built-in passes first, then bundles', then the application's in scan order.
``@compiler_pass`` must be found by the early scan (the application package is).
"""

from __future__ import annotations

from typing import final

from typing_extensions import override
from xtr_dependency_injection import CompilerPassInterface, ContainerBuilder, compiler_pass

__all__ = ["TagApplicationServicesPass"]

_APP_TAG = "bookshop.app_service"


@final
@compiler_pass
class TagApplicationServicesPass(CompilerPassInterface):
    """Tags every definition the application contributed. Bare: ``BEFORE_OPTIMIZATION``, 0.

    It runs after the built-in autoconfiguration passes (priority 100), so decorators
    and autoconfigured definitions are already there to see.
    """

    @override
    def process(self, builder: ContainerBuilder) -> None:
        tagged = 0
        for definition in builder.get_definitions():
            if definition.origin.kind == "app" and not definition.has_tag(_APP_TAG):
                _ = definition.add_tag(_APP_TAG, module=definition.origin.name.split(":")[0])
                tagged += 1
        builder.log(self, f"tagged {tagged} application services")
