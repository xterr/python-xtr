"""Which scopes exist in a deployment, and which a client registered with none is given."""

from __future__ import annotations

from dataclasses import dataclass

from xtr_security_oauth2_server.exception.invalid_configuration_error import (
    InvalidConfigurationError,
)

__all__ = ["ScopesConfig"]


@dataclass(frozen=True, slots=True)
class ScopesConfig:
    """The scopes a deployment knows, and the ones a client registered with none is given.

    ``available`` is the whole vocabulary: a request naming anything else is
    refused, which is what stops a client inventing permissions. The bundle
    reports an empty ``available`` as a missing setting, because a server that
    knows no scope can grant none.

    ``default`` is what a client registered naming no scope is given when it is
    saved. A request naming no scope is granted the scopes its client is
    registered for — never ``default`` itself — so a client that was given the
    defaults is issued them when it asks for none.

    ``default`` may be empty, and that is a real choice rather than an
    oversight: a client registered with no scopes then stays scope-less, the
    unchanged rule that such a client may ask for any scope applies to it, and
    a request naming no scope yields a token carrying none.

    Attributes:
        available: Every scope a client may ask for.
        default: The scopes a client registered with none is given.
    """

    available: tuple[str, ...] = ()
    default: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Refuse an empty scope name, a repeated one, or a default that is not available.

        Raises:
            InvalidConfigurationError: When a scope name is empty, when either
                list repeats a name, or when a default scope is not among the
                available ones — which would hand out a scope every request for
                it is then refused for.
        """
        for name, scopes in (("available", self.available), ("default", self.default)):
            if any(scope == "" for scope in scopes):
                raise InvalidConfigurationError(
                    f"The list scopes.{name} holds an empty scope name; a scope is named by a "
                    "non-empty string.",
                )
            repeated = sorted({scope for scope in scopes if scopes.count(scope) > 1})
            if repeated:
                raise InvalidConfigurationError(
                    f"The list scopes.{name} names {repeated} more than once; each scope is "
                    "named once.",
                )
        unknown = sorted(set(self.default) - set(self.available))
        if unknown:
            raise InvalidConfigurationError(
                f"The default scopes {unknown} are not in scopes.available, so every request "
                f"for them would be refused; add them to scopes.available or drop them from "
                "scopes.default.",
            )
