"""Resolving which authenticator answers a request nothing authenticated."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

from xtr_security.exception import InvalidConfigurationError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_dependency_injection import ServiceKey

    from xtr_security.bundle.security_config import SecurityConfig
    from xtr_security.factory import AuthenticatorFactoryInterface
    from xtr_security.firewall_config import FirewallConfig

__all__ = [
    "ENTRY_POINT_FALLBACK",
    "ENTRY_POINT_NONE",
    "ENTRY_POINT_REAL",
    "resolve_entry_point",
]

ENTRY_POINT_REAL = "real"
"""The kind of an authenticator whose challenge answers an unauthenticated request."""
ENTRY_POINT_NONE = "none"
"""The kind of an authenticator that never answers an unauthenticated request."""
ENTRY_POINT_FALLBACK = "fallback"
"""The kind of an authenticator whose challenge is a last resort, never a first."""


@runtime_checkable
class AnswersEntryPointKind(Protocol):
    """An authenticator factory that says how its authenticator challenges.

    ``entry_point_kind`` answers :data:`ENTRY_POINT_REAL` or
    :data:`ENTRY_POINT_FALLBACK`; a factory that does not answer is read as
    never challenging, so its authenticator is no candidate. The access-token
    factory answers fallback — its bare ``401`` never wins over a real
    challenge when a firewall runs both.
    """

    def entry_point_kind(self, config: object) -> str:
        """Return how the authenticator ``config`` describes answers a challenge."""
        ...


def entry_point_kind(factory: AuthenticatorFactoryInterface, config: object) -> str:
    """Return how the authenticator ``config`` describes answers a challenge.

    A factory answering :meth:`AnswersEntryPointKind.entry_point_kind` is
    believed; any other factory is read as never challenging, so a
    third-party authenticator stays out of the resolution until it adopts
    the protocol.
    """
    answers = cast("object", factory)
    if isinstance(answers, AnswersEntryPointKind):
        return answers.entry_point_kind(config)
    return ENTRY_POINT_NONE


def resolve_entry_point(  # noqa: PLR0913, PLR0917 -- one resolution over one firewall's whole shape
    config: SecurityConfig,
    name: str,
    firewall: FirewallConfig,
    ordered_keys: Sequence[ServiceKey],
    qualifiers: Sequence[str],
    kinds: Sequence[str] = (),
) -> str | None:
    """Resolve the qualifier of the authenticator that answers an unauthenticated request.

    The configured name when given, else — among the authenticators that
    challenge — the only real one; a fallback challenge (the access-token
    authenticator's bare ``401``) never wins over a real one, but answers
    alone when no real one runs. A firewall with an access rule that needs
    authentication and no entry point to answer it fails the build.
    """
    if not ordered_keys:
        return None
    if firewall.entry_point is not None:
        matched = [
            index for index, key in enumerate(ordered_keys) if key[1] == firewall.entry_point
        ]
        if not matched:
            raise InvalidConfigurationError(
                f'The firewall "{name}" names the entry point "{firewall.entry_point}", '
                f"which is not one of its authenticators.",
            )
        return qualifiers[matched[0]]
    needs_auth = any(
        rule.firewall in (None, name) and rule.attribute != "PUBLIC_ACCESS"
        for rule in config.access_control
    )
    if len(ordered_keys) == 1:
        return qualifiers[0]
    real = [index for index, kind in enumerate(kinds) if kind == ENTRY_POINT_REAL]
    if len(real) == 1:
        return qualifiers[real[0]]
    fallback = [index for index, kind in enumerate(kinds) if kind == ENTRY_POINT_FALLBACK]
    if not real and fallback:
        return qualifiers[fallback[0]]
    if needs_auth:
        raise InvalidConfigurationError(
            f'The firewall "{name}" has several authenticators and an access rule that '
            f"needs authentication, but no entry point to answer it; set entry_point.",
        )
    return qualifiers[0]
