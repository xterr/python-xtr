"""The user the claims of an OAuth2 token introspection describe."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast

from typing_extensions import override

from xtr_security_core.exception import InvalidArgumentError

from .user_interface import UserInterface

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = ["OAuth2User"]


class OAuth2User(UserInterface):
    """The user the access-token workflow settles on with an OAuth2 server.

    It carries the standard claims of a token introspection response
    (https://datatracker.ietf.org/doc/html/rfc7662#section-2.2) as read-only
    attributes and keeps every other member as an additional claim. A ``sub``
    or a ``username`` is required; the user is identified by the ``sub`` when
    there is one, by the ``username`` otherwise.

    Neither OIDC nor OAuth has a notion of role: the user holds ``ROLE_USER``
    unless built with other roles — by a provider mapping claims onto roles,
    say.

    Attributes:
        scope: The scopes the token grants, space-separated.
        client_id: The client the token was issued to.
        username: The resource owner who authorized the token.
        token_type: The type of the token.
        exp: When the token expires, as a Unix timestamp.
        iat: When the token was issued, as a Unix timestamp.
        nbf: When the token starts being valid, as a Unix timestamp.
        sub: The subject of the token.
        aud: The audience — one service-specific identifier, or several.
        iss: The issuer of the token.
        jti: The identifier of the token.
        additional_claims: Every other member of the response.
    """

    __slots__: tuple[str, ...] = (
        "_roles",
        "additional_claims",
        "aud",
        "client_id",
        "exp",
        "iat",
        "iss",
        "jti",
        "nbf",
        "scope",
        "sub",
        "token_type",
        "username",
    )

    def __init__(  # noqa: PLR0913, PLR0917 -- one parameter per standard claim, in its order
        self,
        roles: Sequence[str] = ("ROLE_USER",),
        scope: str | None = None,
        client_id: str | None = None,
        username: str | None = None,
        token_type: str | None = None,
        exp: int | None = None,
        iat: int | None = None,
        nbf: int | None = None,
        sub: str | None = None,
        # RFC 7662 §2.2 makes "aud" a service-specific string identifier or
        # list of string identifiers, so a server naming several audiences is
        # not a failure.
        aud: str | Sequence[str] | None = None,
        iss: str | None = None,
        jti: str | None = None,
        **additional_claims: object,
    ) -> None:
        """Record the standard claims, and keep every other member as an additional claim.

        An ``additional_claims`` keyword, when given, is taken as the
        additional claims themselves rather than as one of them.

        Raises:
            InvalidArgumentError: When neither a ``sub`` nor a ``username`` is given.
        """
        if (sub is None or sub == "") and (username is None or username == ""):
            raise InvalidArgumentError('The claim "sub" or "username" must be provided.')
        self._roles: tuple[str, ...] = tuple(roles)
        self.scope: Final = scope
        self.client_id: Final = client_id
        self.username: Final = username
        self.token_type: Final = token_type
        self.exp: Final = exp
        self.iat: Final = iat
        self.nbf: Final = nbf
        self.sub: Final = sub
        self.aud: Final = aud
        self.iss: Final = iss
        self.jti: Final = jti
        nested = additional_claims.get("additional_claims")
        self.additional_claims: Final[Mapping[str, object]] = (
            dict(cast("Mapping[str, object]", nested))
            if "additional_claims" in additional_claims and isinstance(nested, dict)
            else dict(additional_claims)
        )

    @override
    def get_roles(self) -> Sequence[str]:
        """Return the roles granted to this user; ``ROLE_USER`` unless built otherwise."""
        return self._roles

    @override
    def get_user_identifier(self) -> str:
        """Return the ``sub`` claim when there is one, the ``username`` otherwise."""
        return str(self.sub if self.sub is not None else self.username)
