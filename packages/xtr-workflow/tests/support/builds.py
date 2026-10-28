"""A container build to register services into and read definitions back from, without a kernel."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_dependency_injection import ContainerBuilder, Origin, ServiceConfigurator
from xtr_dependency_injection.builder.service_configurator import BuildState

if TYPE_CHECKING:
    from collections.abc import Hashable, Mapping

    from xtr_dependency_injection import Definition

_ORIGIN = Origin("bundle", "workflow")


def build_state(*, debug: bool = False, bundles: tuple[str, ...] = ()) -> BuildState:
    """Return the state of a build in phase ``load``, with ``bundles`` active."""
    state = BuildState(env="test", debug=debug, bundles=("kernel", *bundles), configs={})
    kernel_bundles: Mapping[str, object] = {name: name for name in ("kernel", *bundles)}
    state.add_parameters(
        Origin("kernel", "kernel"), {"kernel": {"debug": debug, "bundles": kernel_bundles}}
    )
    return state


def services_of(state: BuildState) -> ServiceConfigurator:
    return ServiceConfigurator(state, _ORIGIN)


def builder_of(state: BuildState) -> ContainerBuilder:
    return ContainerBuilder(state, _ORIGIN)


def definition_of(
    state: BuildState, service: type, qualifier: Hashable | None = None
) -> Definition:
    definition = state.store.get((service, qualifier))
    assert definition is not None, f"{service.__qualname__}[{qualifier!r}] is not registered"
    return definition
