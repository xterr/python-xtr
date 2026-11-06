"""The configuration the OpenID Connect provider bundle builds from."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

__all__ = ["OpenIdConnectServerConfig"]


@final
@dataclass(frozen=True, slots=True)
class OpenIdConnectServerConfig:
    """Everything this deployment's OpenID Connect provider is configured with.

    It holds no setting yet. It exists, buildable with no arguments, because a
    bundle is declared with the type of its configuration before an
    application has written a line of it, and the provider must build and boot
    on what it is given then.
    """
