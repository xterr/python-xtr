"""The factories of each platform and of the registry over them."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable

from pydantic_ai.settings import ModelSettings
from xtr_dependency_injection import ServiceLocator, named_factory
from xtr_dependency_injection.exception import (
    MissingEnvironmentVariableError,
    ServiceResolutionError,
)

from xtr_ai.exception import PlatformUnavailableError
from xtr_ai.platform import Platform
from xtr_ai.platform_interface import PlatformInterface
from xtr_ai.platform_registry import PlatformRegistry

from .platform_config import PlatformConfig

__all__ = ["platform_factory", "registry_factory"]


def platform_factory(name: str) -> Callable[[PlatformConfig], PlatformInterface]:
    """Build the factory of the platform ``name``, given its configuration as an argument.

    The configuration is the definition's own argument, so the ``env()``
    placeholders it holds are read when this platform is built — and only
    this platform's. It is registered under :class:`PlatformInterface`,
    qualified by its name, where an application's own platform goes too.
    """

    def platform(platform_config: PlatformConfig) -> PlatformInterface:
        return Platform(
            name,
            platform_config.provider,
            api_key=platform_config.api_key,
            base_url=platform_config.base_url,
            options=platform_config.options,
            # Configured as a plain mapping; pydantic-ai reads it as its settings dictionary.
            model_settings=ModelSettings(**platform_config.model_settings) or None,
        )

    platform.__annotations__ = {"platform_config": PlatformConfig, "return": PlatformInterface}
    return named_factory(platform, f"ai_platform_{name}")


def registry_factory(
    names: tuple[str, ...],
) -> Callable[[ServiceLocator[PlatformInterface]], AsyncIterator[PlatformRegistry]]:
    """Build the factory of the registry over ``names``; it closes what it built on the way out."""

    async def ai_platform_registry(
        platforms: ServiceLocator[PlatformInterface],
    ) -> AsyncIterator[PlatformRegistry]:
        async def lookup(name: str) -> PlatformInterface:
            try:
                return await platforms.get(name)
            except ServiceResolutionError as error:
                raise PlatformUnavailableError(name, _reason(error)) from None

        registry = PlatformRegistry(names, lookup)
        try:
            yield registry
        finally:
            await registry.aclose()

    ai_platform_registry.__annotations__ = {
        "platforms": ServiceLocator[PlatformInterface],
        "return": AsyncIterator[PlatformRegistry],
    }
    return ai_platform_registry


def _reason(error: BaseException) -> str:
    """Say why a platform's configuration could not be read, naming a variable but no value."""
    seen: BaseException | None = error
    while seen is not None:
        if isinstance(seen, MissingEnvironmentVariableError):
            return f'the "{seen.name}" environment variable is not set'
        seen = seen.__cause__ or seen.__context__
    return f"its configuration could not be read ({type(error).__name__})"
