"""A builder that sees no peer bundle, for wiring code exercised without a kernel."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder

__all__ = ["NO_PEERS"]


@final
class _NoPeers:
    """Answers that no parameter is set, so ``bundle_active`` reports every peer inactive."""

    def has_parameter(self, name: str) -> bool:
        del name
        return False


NO_PEERS = cast("ContainerBuilder", cast("object", _NoPeers()))
