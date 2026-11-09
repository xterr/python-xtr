"""What a user an identity provider hands back answers to."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from xtr_security_oauth2_server_core.entities.user_entity_interface import UserEntityInterface

from .claim_set_interface import ClaimSetInterface

__all__ = ["UserClaimsEntityInterface"]


@runtime_checkable
class UserClaimsEntityInterface(UserEntityInterface, ClaimSetInterface, Protocol):
    """A resource owner, together with the claims that describe them.

    The authorization server knows a user by identifier alone
    (:class:`~xtr_security_oauth2_server_core.entities.UserEntityInterface`),
    which is all it writes into a token. Describing that user to a client takes
    the claims as well (:class:`ClaimSetInterface`). This is the two at once,
    so the identifier a token names and the claims answered for it come from
    one object, and cannot describe two different users.

    Deliberately empty: each half stands on its own, and this name exists for
    the signature that needs an object to be both — what an identity provider
    hands back.
    """
