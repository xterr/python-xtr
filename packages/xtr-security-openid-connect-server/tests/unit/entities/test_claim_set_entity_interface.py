"""The claim-set contract is runtime-checkable, and asks for both readers."""

from __future__ import annotations

from xtr_security_openid_connect_server.entities.claim_set_entity_interface import (
    ClaimSetEntityInterface,
)


class _ApplicationClaimSet:
    # An application's own class, sharing no base with the package's entity.
    def get_scope(self) -> str:
        return "company"

    def get_claim_names(self) -> tuple[str, ...]:
        return ("company_id",)


class _ScopeOnly:
    def get_scope(self) -> str:
        return "company"


def test_a_class_with_both_readers_satisfies_the_contract() -> None:
    assert isinstance(_ApplicationClaimSet(), ClaimSetEntityInterface)


def test_a_class_naming_only_its_scope_does_not_satisfy_it() -> None:
    assert not isinstance(_ScopeOnly(), ClaimSetEntityInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), ClaimSetEntityInterface)
