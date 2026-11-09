"""The contract a user's claims are read through is runtime-checkable, and asks for them."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_security_openid_connect_server.entities.claim_set_interface import ClaimSetInterface

if TYPE_CHECKING:
    from collections.abc import Mapping


@final
class _ApplicationClaims:
    # An application's own class, sharing no base with the contract.
    async def get_claims(self) -> Mapping[str, object]:
        return {"name": "Alice"}


def test_a_class_reading_its_claims_satisfies_the_contract() -> None:
    claims: ClaimSetInterface = _ApplicationClaims()

    assert isinstance(claims, ClaimSetInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), ClaimSetInterface)
