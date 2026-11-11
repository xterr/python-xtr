"""What code resolving ``<platform>:<model>`` ids depends on."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pydantic_ai.models import AbstractModel, Model, ModelResolutionContext

    from xtr_ai.platform_interface import PlatformInterface

__all__ = ["PlatformRegistryInterface"]


@runtime_checkable
class PlatformRegistryInterface(Protocol):
    """Every configured platform by name, and the model resolver built on them.

    Depend on this rather than on
    :class:`~xtr_ai.platform_registry.PlatformRegistry`. Building a registry,
    and closing what it built, is its owner's business — the container's, or
    whoever made it by hand — and not part of what its users see.
    """

    @property
    def names(self) -> tuple[str, ...]:
        """Every platform's name, in the order given."""
        ...

    def has(self, name: str) -> bool:
        """Whether a platform is configured under ``name``."""
        ...

    async def get(self, name: str) -> PlatformInterface:
        """Return the platform ``name``.

        Raises:
            PlatformUnavailableError: When no platform has that name, or it
                cannot be built.
        """
        ...

    async def model(self, model_id: str) -> Model | None:
        """Return the model ``<platform>:<model>``, or ``None`` when no platform has the prefix.

        Raises:
            PlatformUnavailableError: When the platform cannot be built.
        """
        ...

    async def resolve(self, ctx: ModelResolutionContext[Any], model_id: str) -> Model | None:
        """The resolver ``ResolveModelId`` calls: :meth:`model`, ignoring the context."""
        ...

    def platform_of(self, model: AbstractModel) -> str | None:
        """Return the name of the platform that built ``model``, or ``None`` for any other model."""
        ...
