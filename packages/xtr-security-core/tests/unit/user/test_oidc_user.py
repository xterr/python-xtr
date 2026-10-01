"""The OIDC user is built from the claims a verified token carried."""

from __future__ import annotations

import pytest

from xtr_security_core.exception import InvalidArgumentError
from xtr_security_core.user import OidcUser, UserInterface


def test_it_inherits_the_user_interface() -> None:
    assert UserInterface in OidcUser.__mro__


def test_identifier_from_the_default_claim() -> None:
    user = OidcUser({"sub": "alice", "email": "alice@example.test"})

    assert user.get_user_identifier() == "alice"
    assert user.get_roles() == ("ROLE_USER",)


def test_identifier_from_a_chosen_claim() -> None:
    user = OidcUser({"client_id": "svc-1"}, identifier_claim="client_id")

    assert user.get_user_identifier() == "svc-1"


def test_claims_are_a_defensive_copy() -> None:
    source: dict[str, object] = {"sub": "alice", "n": 1}
    user = OidcUser(source)

    source["n"] = 999

    assert user.claims["n"] == 1


def test_custom_roles() -> None:
    user = OidcUser({"sub": "alice"}, roles=["ROLE_ADMIN"])

    assert user.get_roles() == ("ROLE_ADMIN",)


def test_missing_identifier_claim_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = OidcUser({"email": "alice@example.test"})


def test_empty_identifier_claim_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = OidcUser({"sub": ""})
