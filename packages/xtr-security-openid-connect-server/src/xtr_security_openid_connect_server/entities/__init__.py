"""What a claim set answers to, and the value that meets it.

:class:`ClaimSetEntityInterface` is a contract, not a class to instantiate: the
identity layer reads every claim set through it, and an application may bring
its own. :class:`ClaimSetEntity` is the shortest way to meet it — a scope and
the names of the claims a grant of it reveals, fixed when built.
"""

from __future__ import annotations

from .claim_set_entity import ClaimSetEntity
from .claim_set_entity_interface import ClaimSetEntityInterface

__all__ = [
    "ClaimSetEntity",
    "ClaimSetEntityInterface",
]
