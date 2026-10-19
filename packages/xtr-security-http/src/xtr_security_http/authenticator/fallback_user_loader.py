"""The marker that says a badge's own user loader must be left alone.

The wiring resolves a badge without a loader by giving it the firewall's
user provider — the default word on how a username becomes a user. A badge
that carries its own loader, one the wiring did not build, must keep it:
the loader is the badge's own answer, not a gap for the provider to fill.
This wrapper marks exactly that, while still answering as the loader it
wraps, so the wiring can tell its own loaders from a badge's own with one
``isinstance`` and leave the right ones alone.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["FallbackUserLoader"]


@final
class FallbackUserLoader:
    """Wraps a user loader the wiring must not override, and marks it as such.

    An authenticator that knows how to load its own user — a token's claims
    naming one, a link signing one — hands its badge a loader wrapped here,
    and the wiring leaves it alone. Called, the wrapper answers as the
    loader it wraps; wrapped around ``None``, it answers with no user, the
    badge's own way of saying the wiring should not load one at all.
    """

    __slots__ = ("_inner",)

    def __init__(
        self,
        inner: Callable[..., UserInterface | None] | None = None,
    ) -> None:
        """Wrap ``inner``, the loader the badge owns."""
        self._inner = inner

    def __call__(self, *arguments: object) -> UserInterface | None:
        """Answer as the loader this wrapper wraps, or with no user."""
        if self._inner is None:
            return None
        return self._inner(*arguments)
