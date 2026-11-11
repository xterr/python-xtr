"""One configured model provider, built the first time a run needs it."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final, final

from pydantic_ai.exceptions import UserError
from pydantic_ai.models import Model, infer_model
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.providers import Provider, infer_provider_class
from typing_extensions import override

from xtr_ai._platform_model import PlatformModel
from xtr_ai.exception import InvalidConfigurationError, PlatformUnavailableError
from xtr_ai.platform_interface import PlatformInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

    from pydantic_ai.settings import ModelSettings

__all__ = ["OFFLINE_PROVIDERS", "Platform"]

OFFLINE_PROVIDERS: Final = frozenset({"test", "function"})
"""Provider names served in process, without a key or a network: pydantic-ai's test doubles."""

_NO_OPTIONS: Final[Mapping[str, Any]] = MappingProxyType({})


@final
class Platform(PlatformInterface):
    """A named provider: which one, its key, its endpoint and its other options.

    Nothing is imported or built when a platform is made. The provider — and with
    it the provider's SDK and HTTP client — is built the first time a model is
    asked for, once per platform, so an application whose keys are not set still
    builds, boots and runs its console.

    ``provider`` is any provider name pydantic-ai knows (``openai``,
    ``anthropic``, ``azure``, ``bedrock``, ``google``, ``ollama``, …), so a
    provider pydantic-ai adds needs nothing here. Two more are served in process:
    ``test`` builds pydantic-ai's ``TestModel`` from ``options``, and
    ``function`` builds a ``FunctionModel`` from ``options["function"]`` and/or
    ``options["stream_function"]``.

    ``model_settings`` are this platform's defaults: every model it builds
    carries them, under the agent's settings and the run's.
    """

    __slots__ = (
        "_api_key",
        "_base_url",
        "_model_settings",
        "_models",
        "_name",
        "_options",
        "_provider",
        "_provider_instance",
    )

    def __init__(  # noqa: PLR0913 — one keyword per part of a provider's configuration
        self,
        name: str,
        provider: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        options: Mapping[str, Any] = _NO_OPTIONS,
        model_settings: ModelSettings | None = None,
    ) -> None:
        """Describe the platform; build nothing yet.

        Raises:
            InvalidConfigurationError: When ``name`` or ``provider`` is empty.
        """
        if not name:
            raise InvalidConfigurationError("A platform needs a non-empty name.")
        if not provider:
            raise InvalidConfigurationError(f'The "{name}" platform needs a provider.')
        self._name = name
        self._provider = provider
        self._api_key = api_key
        self._base_url = base_url
        self._options = dict(options)
        self._model_settings = model_settings
        self._provider_instance: Provider[Any] | None = None
        self._models: dict[str, Model] = {}

    @property
    @override
    def name(self) -> str:
        """What the platform is known by: the prefix of its model ids."""
        return self._name

    @property
    @override
    def provider(self) -> str:
        """The provider name, as pydantic-ai knows it."""
        return self._provider

    @property
    def model_settings(self) -> ModelSettings | None:
        """The defaults every model of this platform carries."""
        return self._model_settings

    @property
    def is_offline(self) -> bool:
        """Whether the platform runs in process, with no key and no network."""
        return self._provider in OFFLINE_PROVIDERS

    @override
    def __repr__(self) -> str:
        """Name the platform and its provider; never its key."""
        return f"Platform(name={self._name!r}, provider={self._provider!r})"

    def provider_instance(self) -> Provider[Any]:
        """Return the platform's provider, building it on first use.

        Raises:
            PlatformUnavailableError: When the provider is unknown, its package
                extra is not installed, or it refuses the configuration.
        """
        if self._provider_instance is None:
            self._provider_instance = self._build_provider()
        return self._provider_instance

    @override
    def model(self, model_name: str) -> Model:
        """Return the model ``model_name`` of this platform, building it on first use.

        The same model object is returned every time it is asked for, so its
        provider's HTTP client is shared by every run.

        Raises:
            PlatformUnavailableError: When the provider cannot be built, or
                refuses the model.
        """
        found = self._models.get(model_name)
        if found is None:
            found = self._build_model(model_name)
            if self._model_settings:
                found = PlatformModel(found, self._model_settings)
            self._models[model_name] = found
        return found

    @override
    def built(self, model: object) -> bool:
        """Whether ``model`` is one this platform built."""
        return any(model is own for own in self._models.values())

    @override
    async def aclose(self) -> None:
        """Close the provider's HTTP client, if the platform built one.

        The platform stays usable: a later run opens a client again.
        """
        provider = self._provider_instance
        if provider is None:
            return
        async with provider:
            # Leaving the provider's context is what closes the client it owns.
            pass

    def _build_model(self, model_name: str) -> Model:
        if self._provider == "test":
            return TestModel(model_name=model_name or "test", **self._options)
        if self._provider == "function":
            return self._function_model(model_name)
        provider = self.provider_instance()
        try:
            return infer_model(
                f"{self._provider}:{model_name}", provider_factory=lambda _: provider
            )
        except UserError as error:
            raise PlatformUnavailableError(self._name, str(error)) from error

    def _function_model(self, model_name: str) -> FunctionModel:
        function = self._options.get("function")
        stream_function = self._options.get("stream_function")
        name = model_name or None
        if function is not None and stream_function is not None:
            return FunctionModel(function, stream_function=stream_function, model_name=name)
        if function is not None:
            return FunctionModel(function, model_name=name)
        if stream_function is not None:
            return FunctionModel(stream_function=stream_function, model_name=name)
        raise PlatformUnavailableError(
            self._name,
            'a "function" platform needs options["function"] or options["stream_function"]',
        )

    def _build_provider(self) -> Provider[Any]:
        if self.is_offline:
            raise PlatformUnavailableError(
                self._name, f'the "{self._provider}" provider builds its models in process'
            )
        try:
            provider_class = infer_provider_class(self._provider)
        except ValueError:
            raise PlatformUnavailableError(
                self._name, f'pydantic-ai knows no provider named "{self._provider}"'
            ) from None
        except ImportError as error:
            raise PlatformUnavailableError(
                self._name,
                f'the "{self._provider}" provider needs a package that is not installed '
                f"(xtr-ai forwards pydantic-ai's extras under the same names): {error}",
            ) from error
        keywords: dict[str, Any] = dict(self._options)
        if self._api_key is not None:
            keywords["api_key"] = self._api_key
        if self._base_url is not None:
            keywords["base_url"] = self._base_url
        try:
            return provider_class(**keywords)
        except TypeError:
            # The provider's own message may repeat the values it was given; name the keywords only.
            raise PlatformUnavailableError(
                self._name,
                f"the {provider_class.__name__} provider does not take the keywords "
                f"{sorted(keywords)}",
            ) from None
        except UserError as error:
            raise PlatformUnavailableError(self._name, str(error)) from error
        except Exception as error:
            # The provider's SDK refused it, in an error of its own — OpenAI's for a missing key,
            # say. Its message may carry what it was given, so only its type is named here.
            raise PlatformUnavailableError(
                self._name,
                f"the {provider_class.__name__} provider refused its configuration "
                f"({type(error).__qualname__}); check its key and options",
            ) from error
