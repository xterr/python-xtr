"""The add-on's own service, which its answer cannot be built without."""

from __future__ import annotations

from typing import Final, final

__all__ = ["STAMP_PREFIX", "NonceStamp"]

#: What the add-on's field is stamped with, so a test can tell the value apart
#: from the parameter it was built from.
STAMP_PREFIX: Final[str] = "stamped"


@final
class NonceStamp:
    """Turns a parameter carried across the consent step into a published value.

    A service of the add-on's own, registered by the add-on's bundle. The
    answer below takes it in its constructor, which is why the response type a
    deployment names is registered as a service rather than built by the
    server: an add-on's answer needs its add-on's services.
    """

    __slots__ = ()

    def stamp(self, nonce: str) -> str:
        """Return what the add-on publishes for the carried ``nonce``."""
        return f"{STAMP_PREFIX}:{nonce}"
