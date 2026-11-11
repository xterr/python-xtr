"""What code reaching a model provider depends on."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pydantic_ai.models import Model

__all__ = ["PlatformInterface"]


@runtime_checkable
class PlatformInterface(Protocol):
    """A named source of models: one provider, reached one way.

    Depend on this rather than on :class:`~xtr_ai.platform.Platform`, and a
    platform of the application's own — models from a client it already
    holds, a gateway, a recorded double — goes wherever a configured one does:
    into :class:`~xtr_ai.platform_registry.PlatformRegistry`, or registered in
    the container under this interface, qualified by its name.
    """

    @property
    def name(self) -> str:
        """What the platform is known by: the prefix of its model ids."""
        ...

    @property
    def provider(self) -> str:
        """The provider the platform reaches, as pydantic-ai names it."""
        ...

    def model(self, model_name: str) -> Model:
        """Return the model ``model_name`` of this platform.

        Asked for again, the same model is returned, so every run shares its
        client.

        Raises:
            PlatformUnavailableError: When the platform cannot build it.
        """
        ...

    def built(self, model: object) -> bool:
        """Whether ``model`` is one this platform returned from :meth:`model`."""
        ...

    async def aclose(self) -> None:
        """Release what the platform opened, such as its HTTP client.

        The platform stays usable: a later model opens what it needs again.
        """
        ...
