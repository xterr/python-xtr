"""Which of a user's claims the scopes a token was granted reveal.

A user holds claims — a name, an email address, a phone number — and a token
reveals only the ones its scopes open up. Each scope that opens any up has a
claim set naming them: :class:`ClaimExtractor` holds the sets, starting with
those of the four scopes OpenID Connect Core defines (Section 5.4), and picks a
user's claims through them.
"""

from __future__ import annotations

from collections.abc import (
    Iterable,  # noqa: TC003 -- container hydrates this constructor at runtime
)
from typing import TYPE_CHECKING, Final, final

from xtr_security_openid_connect_server.entities.claim_set_entity import ClaimSetEntity
from xtr_security_openid_connect_server.entities.claim_set_entity_interface import (
    ClaimSetEntityInterface,  # noqa: TC001 -- container hydrates this constructor at runtime
)
from xtr_security_openid_connect_server.exception.invalid_argument_error import (
    InvalidArgumentError,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["ClaimExtractor"]

#: The scopes OpenID Connect Core defines, each with the claims a grant of it
#: reveals, in the order the protocol lists them (Section 5.4).
_PROTOCOL_CLAIM_SETS: Final = (
    ClaimSetEntity(
        "profile",
        (
            "name",
            "family_name",
            "given_name",
            "middle_name",
            "nickname",
            "preferred_username",
            "profile",
            "picture",
            "website",
            "gender",
            "birthdate",
            "zoneinfo",
            "locale",
            "updated_at",
        ),
    ),
    ClaimSetEntity("email", ("email", "email_verified")),
    ClaimSetEntity("address", ("address",)),
    ClaimSetEntity("phone", ("phone_number", "phone_number_verified")),
)

#: The scopes whose claims the protocol fixes, so no set may stand in for theirs.
_PROTECTED_SCOPES: Final = frozenset(claim_set.get_scope() for claim_set in _PROTOCOL_CLAIM_SETS)


@final
class ClaimExtractor:
    """Picks out of a user's claims the ones the scopes they granted reveal.

    A token is granted scopes, and each scope reveals the claims its set
    names; whatever else the user holds stays undisclosed, and a scope with no
    set — ``openid`` itself, or a plain permission — reveals nothing.

    The four scopes OpenID Connect Core defines come held, with the claims the
    protocol pairs each with, and an application adds sets for scopes of its
    own. The protocol's four cannot be changed: an end-user granting ``email``
    agrees to share what the protocol says ``email`` reveals, and a set
    redefining it would hand a client other claims under the name the end-user
    agreed to.

    Built once and shared by every request: extracting waits on nothing and
    changes nothing.
    """

    __slots__ = ("_claim_sets",)

    def __init__(self, claim_sets: Iterable[ClaimSetEntityInterface] = ()) -> None:
        """Hold the protocol's four sets, then ``claim_sets`` in the order given.

        Raises:
            InvalidArgumentError: When one of ``claim_sets`` is for a scope the
                protocol defines.
        """
        self._claim_sets: dict[str, ClaimSetEntityInterface] = {
            claim_set.get_scope(): claim_set for claim_set in _PROTOCOL_CLAIM_SETS
        }
        for claim_set in claim_sets:
            self.add_claim_set(claim_set)

    def add_claim_set(self, claim_set: ClaimSetEntityInterface) -> None:
        """Hold ``claim_set``, in the place of any set already held for its scope.

        Raises:
            InvalidArgumentError: When the set is for a scope the protocol
                defines, whose claims are not a deployment's to change.
        """
        scope = claim_set.get_scope()
        if scope in _PROTECTED_SCOPES:
            raise InvalidArgumentError(
                f"The {scope!r} scope is one OpenID Connect Core defines, and so are the "
                "claims it reveals: a claim set cannot change them. Give these claims a "
                "scope of the application's own.",
            )
        self._claim_sets[scope] = claim_set

    def get_claim_set(self, scope: str) -> ClaimSetEntityInterface | None:
        """Return the set held for ``scope``, or ``None`` when it holds none."""
        return self._claim_sets.get(scope)

    def has_claim_set(self, scope: str) -> bool:
        """Return whether a set is held for ``scope``."""
        return scope in self._claim_sets

    def get_claim_sets(self) -> tuple[ClaimSetEntityInterface, ...]:
        """Return every set held: the protocol's four, then the others in the order added.

        Between them they name every claim this server can ever reveal, which
        is what a client is told the server supports.
        """
        return tuple(self._claim_sets.values())

    def extract(self, scopes: Iterable[str], claims: Mapping[str, object]) -> dict[str, object]:
        """Return the claims out of ``claims`` that ``scopes`` reveal.

        A claim is revealed when the set of a granted scope names it and the
        user holds it. One the user does not hold is left out rather than
        answered empty, which would say they hold an empty one. A claim two
        granted scopes both name is revealed once.

        Args:
            scopes: The scopes the token was granted.
            claims: Every claim the user holds, by name.

        Returns:
            The revealed claims, by name; empty when no granted scope reveals
            any.
        """
        revealed: dict[str, object] = {}
        for scope in scopes:
            claim_set = self.get_claim_set(scope)
            if claim_set is None:
                continue
            revealed.update(
                {name: claims[name] for name in claim_set.get_claim_names() if name in claims},
            )

        return revealed
