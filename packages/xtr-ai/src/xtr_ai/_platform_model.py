"""A model carrying its platform's default settings."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.settings import merge_model_settings
from typing_extensions import override

if TYPE_CHECKING:
    from pydantic_ai.models import Model
    from pydantic_ai.settings import ModelSettings

__all__ = ["PlatformModel"]


# Not final: pydantic-ai's model base declares instance state its own wrapper leaves to the
# wrapped model, which a final subclass would be required to initialise itself.
class PlatformModel(WrapperModel):
    """The model a platform built, with the platform's defaults as its own settings.

    A model's own settings are the lowest layer pydantic-ai merges — under the
    agent's, a capability's and the run's — so a platform default holds only
    where nothing above it sets the same key, and travels with the model when a
    run switches to it or falls back to it.
    """

    def __init__(self, wrapped: Model, platform_settings: ModelSettings) -> None:
        """Wrap ``wrapped``, carrying ``platform_settings`` under its own."""
        super().__init__(wrapped)
        self._platform_settings: ModelSettings = platform_settings

    @property
    @override
    def settings(self) -> ModelSettings | None:
        """The platform's defaults, with the wrapped model's own settings over them."""
        return merge_model_settings(self._platform_settings, self.wrapped.settings)
