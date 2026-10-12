"""A container builder a compiler pass can be run against on its own.

A pass is handed a builder in phase ``process`` and nothing else, so one can be
driven without a kernel: the state below is the real one the compiler owns, with
the parameters and definitions a test wants in it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_dependency_injection import ContainerBuilder, Origin
from xtr_dependency_injection.builder.service_configurator import BuildState

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["processing_builder"]

#: Who the definitions a test adds belong to.
_ORIGIN = Origin("bundle", "oauth2_server")


def processing_builder(parameters: Mapping[str, object] | None = None) -> ContainerBuilder:
    """Return a builder in the phase a pass runs in, holding ``parameters``."""
    state = BuildState(env="test", debug=True, bundles=(), configs={}, phase="process")
    if parameters is not None:
        state.add_parameters(_ORIGIN, parameters)

    return ContainerBuilder(state, _ORIGIN)
