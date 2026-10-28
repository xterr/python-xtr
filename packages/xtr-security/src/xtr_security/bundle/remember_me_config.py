"""A remember-me authenticator, described as inert data.

The cookie a login leaves behind is signed — over the user's covered
properties, until a lifetime from now — or persisted as a series of values
the application's token provider keeps; either way the request that presents
it is the request the last login remembered. The secret the value is signed
with is the application's to supply: the bundle builds and boots without it,
and the handler that needs it fails naming it the first time it is asked for.
"""

from __future__ import annotations

from collections.abc import Sequence  # noqa: TC003 -- field type read at runtime
from dataclasses import dataclass
from typing import Literal

from xtr_security.exception import InvalidConfigurationError

__all__ = ["RememberMeConfig", "RememberMeHandlerName"]

RememberMeHandlerName = Literal["signature", "persistent"]
"""Which handler holds the cookie: a signed value, or a persisted series."""


@dataclass(frozen=True, slots=True)
class RememberMeConfig:
    """A remember-me authenticator: the cookie that outlives the session.

    Attributes:
        handler: Which handler stages and spends the cookie — ``"signature"``
            for a value signed over the user's covered properties, or
            ``"persistent"`` for a series of values the application's token
            provider keeps, detecting theft by a series replaying a value its
            provider no longer holds.
        secret: The secret the cookie's value is signed with — the
            application's to supply, never generated. Checked where it is
            used: the bundle builds and boots without it, and the handler
            fails naming it the first time it is asked for.
        name: The name the cookie travels under.
        lifetime: How many seconds the cookie lives for.
        path: The path the cookie answers on.
        domain: The domain the cookie answers on, or ``None`` for the
            request's own host.
        secure: Whether the cookie travels over HTTPS only.
        httponly: Whether the cookie is hidden from the page's scripts.
        samesite: The cross-site policy the cookie carries — ``"lax"``,
            ``"strict"``, ``"none"`` — or ``None`` for the browser's default.
        always_remember_me: Whether every login is remembered without the
            request asking.
        remember_me_parameter: The name a request carries its ask under.
        signature_properties: The user properties whose digest a persisted
            value carries, retiring the series when any of them changes;
            the password alone when ``None``.
        token_provider: The qualifier of the application's
            :class:`~xtr_security_core.user.token_provider_interface.TokenProviderInterface`
            service a persistent handler keeps its series in — required by
            the persistent handler, checked where it is used, never at build.
        success_handler: The application's own success-handler service type,
            or ``None`` for the default redirect by the target ladder.
        failure_handler: The application's own failure-handler service type,
            or ``None`` for the default redirect to the login page.

    Raises:
        InvalidConfigurationError: When the handler is unknown.
    """

    handler: RememberMeHandlerName = "signature"
    secret: str | None = None
    name: str = "REMEMBERME"
    lifetime: int = 31536000
    path: str = "/"
    domain: str | None = None
    secure: bool = False
    httponly: bool = True
    samesite: str | None = None
    always_remember_me: bool = False
    remember_me_parameter: str = "_remember_me"
    signature_properties: Sequence[str] | None = None
    token_provider: str | None = None
    success_handler: type | None = None
    failure_handler: type | None = None

    def __post_init__(self) -> None:
        """Refuse a handler the bundle cannot build."""
        if self.handler not in ("signature", "persistent"):
            raise InvalidConfigurationError(
                f"Unknown remember-me handler {self.handler!r}; "
                f'known are "signature" and "persistent".',
            )

    def to_options(self) -> dict[str, object]:
        """Return the cookie's shape as the handler's options read it."""
        return {
            "name": self.name,
            "lifetime": self.lifetime,
            "path": self.path,
            "domain": self.domain,
            "secure": self.secure,
            "httponly": self.httponly,
            "samesite": self.samesite,
            "always_remember_me": self.always_remember_me,
            "remember_me_parameter": self.remember_me_parameter,
        }
