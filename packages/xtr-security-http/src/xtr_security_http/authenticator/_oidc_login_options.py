"""The options an OIDC login runs under, merged over the defaults and validated."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Final, cast, final

from xtr_security_core.exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = ["OidcLoginOptions", "managed_params_of"]

#: The parameters of the authorization request the authenticator computes
#: itself, so that no configuration can weaken them. "max_age" is owned too,
#: as sending it obliges this client to check the "auth_time" claim of the
#: resulting ID token. "dpop_jkt" is owned though no proof factory exists
#: here yet: a listener has no more right to speak for a key this stack
#: cannot bind the code to than for the state it computes.
MANAGED_PARAMS: Final[frozenset[str]] = frozenset(
    {
        "response_type",
        "client_id",
        "redirect_uri",
        "scope",
        "state",
        "nonce",
        "code_challenge",
        "code_challenge_method",
        "max_age",
        "dpop_jkt",
    },
)

_PKCE_METHODS: Final = ("S256", "plain")
"""The PKCE code challenge methods RFC 7636, Section 4.2 defines."""

_SCOPE_SPLIT: Final = re.compile(r"\s+")


def managed_params_of(params: Mapping[str, str]) -> list[str]:
    """Return the managed parameters ``params`` carries, in a stable order.

    Raises:
        InvalidArgumentError: When ``params`` carries any, which the caller
            is then refusing on the authenticator's behalf.
    """
    managed = sorted(name for name in params if name in MANAGED_PARAMS)
    if managed:
        quoted = '", "'.join(managed)
        raise InvalidArgumentError(
            f'The authorization request parameter(s) "{quoted}" are managed by '
            "the authenticator and cannot be set through the authorization params.",
        )
    return managed


@final
@dataclass(frozen=True, slots=True)
class OidcLoginOptions:
    """The shape of one OIDC login: where the callback arrives, what it asks for.

    Merged over the defaults by :meth:`merge`, and validated where a wrong
    value would weaken the flow rather than fail it loudly.
    """

    CHECK_PATH: ClassVar[str] = "/oidc/callback"
    """Where the provider sends the authorization response, by default."""

    FIREWALL_NAME: ClassVar[str] = "main"
    """The firewall the login runs under, by default."""

    check_path: str = CHECK_PATH
    firewall_name: str = FIREWALL_NAME
    scope: tuple[str, ...] = ("openid",)
    pkce_enabled: bool = True
    pkce_method: str = "S256"
    user_data_source: str = "userinfo"
    user_identifier_claim: str = "sub"
    max_age: int | None = None

    def __post_init__(self) -> None:
        """Refuse a PKCE method RFC 7636 does not define.

        Raises:
            InvalidArgumentError: When ``pkce_method`` names neither
                ``"S256"`` nor ``"plain"``.
        """
        if self.pkce_method not in _PKCE_METHODS:
            raise InvalidArgumentError(
                f'Invalid PKCE method "{self.pkce_method}": '
                'RFC 7636 defines "S256" and "plain" only.',
            )

    @classmethod
    def merge(cls, options: Mapping[str, object] | None) -> OidcLoginOptions:
        """Build the options over the defaults, from a wiring-supplied mapping.

        Args:
            options: The options the wiring configured, merged over the
                defaults; ``None`` is the defaults as they are.
        """
        given = dict(options or {})
        scope = given.get("scope")
        if isinstance(scope, str):
            parts: tuple[str, ...] = (scope,)
        elif isinstance(scope, (tuple, list)):
            parts = tuple(str(part) for part in cast("Sequence[object]", scope))
        else:
            parts = ("openid",)
        max_age = given.get("max_age")
        return cls(
            check_path=str(given.get("check_path", cls.CHECK_PATH)),
            firewall_name=str(given.get("firewall_name", cls.FIREWALL_NAME)),
            scope=parts,
            pkce_enabled=bool(given.get("pkce_enabled", True)),
            pkce_method=str(given.get("pkce_method", "S256")),
            user_data_source=str(given.get("user_data_source", "userinfo")),
            user_identifier_claim=str(given.get("user_identifier_claim", "sub")),
            max_age=max_age if isinstance(max_age, int) and not isinstance(max_age, bool) else None,
        )

    def scopes(self) -> tuple[str, ...]:
        """Return the scopes of the authorization request, always with ``openid`` first.

        OIDC Core 1.0, Section 3.1.2.1 requires that one for the request to
        return an ID token. Each configured value may hold several
        space-separated scopes, so that an environment variable can carry
        them all.
        """
        scopes: list[str] = ["openid"]
        for value in self.scope:
            scopes.extend(part for part in _SCOPE_SPLIT.split(str(value)) if part)
        return tuple(dict.fromkeys(scopes))
