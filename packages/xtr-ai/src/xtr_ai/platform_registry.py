"""Every configured platform by name, and the model resolver built on them."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, final

from typing_extensions import override

from xtr_ai.exception import PlatformUnavailableError
from xtr_ai.platform_registry_interface import PlatformRegistryInterface

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterable

    from pydantic_ai.models import AbstractModel, Model, ModelResolutionContext

    from xtr_ai.platform_interface import PlatformInterface

__all__ = ["PlatformRegistry"]


@final
class PlatformRegistry(PlatformRegistryInterface):
    """Resolves ``<platform>:<model>`` ids through the configured platforms.

    Each platform is asked for only when a model of it is, through ``lookup``,
    so a platform whose configuration reads the environment reads it then and
    not before. Pass :meth:`resolve` to pydantic-ai's ``ResolveModelId``
    capability and every agent, fallback and per-run ``model=`` naming a
    platform resolves here; an id whose prefix names no platform is left to
    pydantic-ai's own inference.

    Any :class:`~xtr_ai.platform_interface.PlatformInterface` serves, not only
    a :class:`~xtr_ai.platform.Platform`.

    ```python
    registry = PlatformRegistry.of(
        Platform("local", "openai", base_url="http://localhost:11434/v1")
    )
    agent = Agent("local:llama-3.3-70b", capabilities=[ResolveModelId(registry.resolve)])
    ```
    """

    __slots__ = ("_built", "_lookup", "_names")

    def __init__(
        self, names: Iterable[str], lookup: Callable[[str], Awaitable[PlatformInterface]]
    ) -> None:
        """Know the platforms by ``names``; build each through ``lookup`` when first needed."""
        self._names = tuple(names)
        self._lookup = lookup
        self._built: dict[str, PlatformInterface] = {}

    @classmethod
    def of(cls, *platforms: PlatformInterface) -> PlatformRegistry:
        """Return a registry over platforms already made."""
        by_name = {platform.name: platform for platform in platforms}

        async def lookup(name: str) -> PlatformInterface:
            return by_name[name]

        return cls(by_name, lookup)

    @property
    @override
    def names(self) -> tuple[str, ...]:
        """Every platform's name, in the order given."""
        return self._names

    @override
    def has(self, name: str) -> bool:
        """Whether a platform is configured under ``name``."""
        return name in self._names

    @override
    async def get(self, name: str) -> PlatformInterface:
        """Return the platform ``name``.

        Raises:
            PlatformUnavailableError: When no platform has that name, or
                ``lookup`` could not build it.
        """
        found = self._built.get(name)
        if found is not None:
            return found
        if name not in self._names:
            configured = ", ".join(f'"{known}"' for known in self._names) or "none"
            raise PlatformUnavailableError(
                name, f"no platform of that name is configured (configured: {configured})"
            )
        found = await self._lookup(name)
        self._built[name] = found
        return found

    @override
    async def model(self, model_id: str) -> Model | None:
        """Return the model ``<platform>:<model>``, or ``None`` when no platform has the prefix.

        Raises:
            PlatformUnavailableError: When the platform cannot be built.
        """
        platform_name, separator, model_name = model_id.partition(":")
        if not separator or platform_name not in self._names:
            return None
        platform = await self.get(platform_name)
        return platform.model(model_name)

    @override
    async def resolve(self, ctx: ModelResolutionContext[Any], model_id: str) -> Model | None:
        """The resolver ``ResolveModelId`` calls: :meth:`model`, ignoring the context."""
        del ctx
        return await self.model(model_id)

    @override
    def platform_of(self, model: AbstractModel) -> str | None:
        """Return the name of the platform that built ``model``, or ``None`` for any other model."""
        for name, platform in self._built.items():
            if platform.built(model):
                return name
        return None

    async def aclose(self) -> None:
        """Close every platform this registry built."""
        for platform in self._built.values():
            await platform.aclose()
