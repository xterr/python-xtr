"""The scope a set of claims belongs to, and the names of those claims."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from typing_extensions import override

from xtr_security_openid_connect_server.exception.invalid_argument_error import (
    InvalidArgumentError,
)

from .claim_set_entity_interface import ClaimSetEntityInterface

__all__ = ["ClaimSetEntity"]


@final
@dataclass(frozen=True, slots=True)
class ClaimSetEntity(ClaimSetEntityInterface):
    """A scope and the claims a grant of it reveals, fixed when built.

    A token granted ``email`` lets its holder read the user's ``email`` and
    ``email_verified``, and nothing else; that pairing is what this records.
    The protocol fixes the pairing for its own scopes, and a deployment adds
    sets for scopes of its own — ``company`` revealing ``company_id``, say.

    Frozen, because one set is shared by every request a deployment answers: a
    set changed while one request reads it would reveal other claims to the
    next.

    Attributes:
        scope: The scope whose grant reveals the claims.
        claim_names: The names of the claims it reveals, in the order declared;
            empty for a scope that reveals none.
    """

    scope: str
    claim_names: tuple[str, ...]

    def __post_init__(self) -> None:
        """Refuse a set naming no scope.

        Raises:
            InvalidArgumentError: When ``scope`` is empty.
        """
        if self.scope == "":
            raise InvalidArgumentError(
                "A claim set has to name the scope that reveals its claims; the set of "
                f"{self.claim_names!r} names none, so no grant could ever reveal them.",
            )

    @override
    def get_scope(self) -> str:
        """Return the scope whose grant reveals these claims."""
        return self.scope

    @override
    def get_claim_names(self) -> tuple[str, ...]:
        """Return the names of the claims the scope reveals, in the order declared."""
        return self.claim_names
