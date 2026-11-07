"""What the identity layer reads claims through: a scope's, and a user's.

:class:`ClaimSetEntityInterface` is a contract, not a class to instantiate: the
identity layer reads every claim set through it, and an application may bring
its own. :class:`ClaimSetEntity` is the shortest way to meet it — a scope and
the names of the claims a grant of it reveals, fixed when built.

:class:`ClaimSetInterface` holds the other half: the claims a user has, name
to value. :class:`UserClaimsEntityInterface` joins it to the resource owner the
authorization server knows by identifier — what an identity provider hands
back, and what an application implements on its own user class.
"""

from __future__ import annotations

from .claim_set_entity import ClaimSetEntity
from .claim_set_entity_interface import ClaimSetEntityInterface
from .claim_set_interface import ClaimSetInterface
from .user_claims_entity_interface import UserClaimsEntityInterface

__all__ = [
    "ClaimSetEntity",
    "ClaimSetEntityInterface",
    "ClaimSetInterface",
    "UserClaimsEntityInterface",
]
