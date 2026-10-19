"""The sender-constraint interface is a runtime-checkable protocol."""

from __future__ import annotations

import re

import pytest
from xtr_security_core.exception import BadCredentialsError

from tests.support.http import FakeSenderConstraint
from tests.support.messages import make_message
from xtr_security_http.access_token.sender_constraint_interface import (
    SenderConstraintInterface,
)

pytestmark = pytest.mark.anyio


def test_a_conforming_constraint_satisfies_the_interface() -> None:
    assert isinstance(FakeSenderConstraint(), SenderConstraintInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), SenderConstraintInterface)


async def test_the_fake_records_what_it_weighed() -> None:
    constraint = FakeSenderConstraint()
    request = make_message()

    await constraint.check(request, "a-token", {"cnf": {"jkt": "thumbprint"}})

    assert constraint.checked == (request, "a-token", {"cnf": {"jkt": "thumbprint"}})


async def test_the_fake_refuses_when_configured_to() -> None:
    refusal = BadCredentialsError("The proof does not check out.")
    constraint = FakeSenderConstraint(refusal=refusal)

    with pytest.raises(BadCredentialsError, match=re.escape("The proof does not check out.")):
        await constraint.check(make_message(), "a-token", {})


def test_the_fake_answers_the_configured_challenge() -> None:
    constraint = FakeSenderConstraint(scheme="DPoP", parameters={"error": "use_dpop_nonce"})

    scheme, parameters = constraint.get_challenge(None)

    assert scheme == "DPoP"
    assert parameters == {"error": "use_dpop_nonce"}
    assert constraint.challenged == [None]
