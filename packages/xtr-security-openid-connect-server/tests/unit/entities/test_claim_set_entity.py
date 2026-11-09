"""A claim set names a scope and the claims a grant of it reveals."""

from __future__ import annotations

import dataclasses

import pytest

from xtr_security_openid_connect_server.entities import ClaimSetEntity, ClaimSetEntityInterface
from xtr_security_openid_connect_server.exception.invalid_argument_error import (
    InvalidArgumentError,
)


def test_it_reads_back_the_scope_it_belongs_to() -> None:
    assert ClaimSetEntity("email", ("email", "email_verified")).get_scope() == "email"


def test_it_reads_back_the_claim_names_in_the_order_declared() -> None:
    claim_set = ClaimSetEntity("email", ("email", "email_verified"))

    assert claim_set.get_claim_names() == ("email", "email_verified")


def test_a_scope_may_reveal_no_claims() -> None:
    assert ClaimSetEntity("audit", ()).get_claim_names() == ()


def test_it_satisfies_the_claim_set_contract() -> None:
    assert isinstance(ClaimSetEntity("email", ("email",)), ClaimSetEntityInterface)


def test_a_claim_set_naming_no_scope_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match=r"scope"):
        _ = ClaimSetEntity("", ())


def test_it_cannot_be_changed_once_built() -> None:
    claim_set = ClaimSetEntity("email", ("email",))
    field = "scope"

    with pytest.raises(dataclasses.FrozenInstanceError):
        # Through setattr: the type checkers refuse the assignment on sight, and
        # what is tested here is that the runtime refuses it too.
        setattr(claim_set, field, "phone")
