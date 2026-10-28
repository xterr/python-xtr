"""A cookie a logout clears, as it was set."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["ClearedCookie"]


@dataclass(frozen=True, slots=True)
class ClearedCookie:
    """The attributes a cookie was set with, which clearing it must repeat.

    A browser tells cookies apart by their name, path and domain together,
    so the header that clears one must repeat the path and the domain it was
    set with — clearing ``name`` alone would leave a cookie set under
    another path or domain untouched.

    Attributes:
        path: The path the cookie was set under; the whole site by default.
        domain: The domain the cookie was set to; every host that reads it
            when ``None``.
        secure: Whether the cookie was set to travel only over a secure
            connection.
        samesite: The cross-site rule the cookie was set with — ``"lax"``,
            ``"strict"`` or ``"none"`` — or ``None`` when it was set with
            none.
    """

    path: str = "/"
    domain: str | None = None
    secure: bool = False
    samesite: str | None = None
