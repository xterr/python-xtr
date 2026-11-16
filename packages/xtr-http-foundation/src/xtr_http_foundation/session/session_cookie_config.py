"""The shape of the cookie a session's ID travels in."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from xtr_http_foundation.exception import InvalidArgumentError

__all__ = ["SessionCookieConfig"]

_SAMESITE_VALUES = ("lax", "none", "strict")


@final
@dataclass(frozen=True, slots=True)
class SessionCookieConfig:
    """The cookie a session's ID travels in, as the response writes it.

    The shape is configuration, validated once where it is built, so a
    cookie no browser would keep is refused at wiring time rather than at
    the first response. The lifetime is the application's notion of how
    long a session lives: the cookie is dated by it, and the storage entry
    is written to live as long — a lifetime of ``None`` is the browser
    session, which names no moment to expire at, and the storage falls
    back to the lifetime it is configured with.

    What cannot sit in a ``Set-Cookie`` attribute at all — a path or a
    domain carrying the separators of the attributes that follow — is
    refused by the header builder the cookie is written through, which
    owns those rules once for every cookie it builds.

    Attributes:
        name: The cookie's name.
        path: The path the cookie is available under; the whole site by
            default.
        domain: The domain the cookie is available to; every host that
            reads it when ``None``.
        secure: Whether the cookie travels only over a secure connection;
            ``None``, the default, makes it ``Secure`` exactly when the
            request it answers came over https. Behind a proxy that ends
            TLS, the scheme is https only where the server reads the
            proxy's forwarded headers.
        httponly: Whether the cookie stays out of the scripts a page runs.
        samesite: Whether the cookie travels on cross-site requests —
            ``"lax"``, ``"strict"`` or ``"none"``, read without regard to
            case; ``None`` or ``""`` writes no attribute.
        lifetime: How many seconds the session lives, or ``None`` for one
            that expires with the browser session.
    """

    name: str = "xtr_session"
    path: str | None = "/"
    domain: str | None = None
    secure: bool | None = None
    httponly: bool = True
    samesite: str | None = "lax"
    lifetime: int | None = None

    def __post_init__(self) -> None:
        """Refuse a cookie no browser would keep.

        Raises:
            InvalidArgumentError: When the name is empty, when ``samesite``
                is none of the three, when the lifetime is negative, or when
                a cookie said not to be secure has ``samesite="none"`` or a
                ``__Host-``/``__Secure-`` name — both of which a browser
                drops unless the cookie is secure.
        """
        if not self.name:
            raise InvalidArgumentError("The session cookie name cannot be empty.")

        if self.samesite not in (None, "") and self.samesite.lower() not in _SAMESITE_VALUES:
            raise InvalidArgumentError(
                f'"{self.samesite}" is not a samesite value: use "lax", "strict", "none" or None.',
            )

        if self.lifetime is not None and self.lifetime < 0:
            raise InvalidArgumentError(
                f"The session lifetime cannot be negative: {self.lifetime}.",
            )

        if self.secure is False and (self.samesite or "").lower() == "none":
            raise InvalidArgumentError(
                'A samesite="none" cookie must be secure: leave secure unset or set it True.',
            )

        if self.secure is False and self.name.startswith(("__Host-", "__Secure-")):
            raise InvalidArgumentError(
                f'The cookie name "{self.name}" uses a reserved prefix, '
                "which needs a secure cookie.",
            )
