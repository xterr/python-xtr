"""The claim extractor picks out of a user's claims the ones their granted scopes reveal."""

from __future__ import annotations

import pytest

from xtr_security_openid_connect_server.claim_extractor import ClaimExtractor
from xtr_security_openid_connect_server.entities import ClaimSetEntity
from xtr_security_openid_connect_server.exception.invalid_argument_error import (
    InvalidArgumentError,
)


def test_it_comes_with_the_claims_openid_connect_core_pairs_with_its_four_scopes() -> None:
    revealed_by_scope = {
        claim_set.get_scope(): claim_set.get_claim_names()
        for claim_set in ClaimExtractor().get_claim_sets()
    }

    assert revealed_by_scope == {
        "profile": (
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
        "email": ("email", "email_verified"),
        "address": ("address",),
        "phone": ("phone_number", "phone_number_verified"),
    }


def test_the_protocol_sets_come_first_in_the_order_the_protocol_lists_them() -> None:
    claim_sets = ClaimExtractor().get_claim_sets()

    assert [claim_set.get_scope() for claim_set in claim_sets] == [
        "profile",
        "email",
        "address",
        "phone",
    ]


def test_a_set_added_later_comes_back_last() -> None:
    extractor = ClaimExtractor()
    company = ClaimSetEntity("company", ("company_id",))

    extractor.add_claim_set(company)

    assert extractor.get_claim_sets()[-1] is company


def test_the_sets_it_is_built_with_come_after_the_protocol_ones_in_the_order_given() -> None:
    company = ClaimSetEntity("company", ("company_id",))
    team = ClaimSetEntity("team", ("team_id",))

    extractor = ClaimExtractor([company, team])

    assert [claim_set.get_scope() for claim_set in extractor.get_claim_sets()] == [
        "profile",
        "email",
        "address",
        "phone",
        "company",
        "team",
    ]


def test_it_hands_out_the_set_registered_for_a_scope() -> None:
    company = ClaimSetEntity("company", ("company_id",))

    assert ClaimExtractor([company]).get_claim_set("company") is company


def test_it_hands_out_no_set_for_a_scope_it_holds_none_for() -> None:
    assert ClaimExtractor().get_claim_set("openid") is None


@pytest.mark.parametrize(
    ("scope", "expected"),
    [("email", True), ("company", True), ("openid", False)],
)
def test_it_tells_whether_it_holds_a_set_for_a_scope(scope: str, expected: bool) -> None:
    extractor = ClaimExtractor([ClaimSetEntity("company", ("company_id",))])

    assert extractor.has_claim_set(scope) is expected


def test_a_set_for_an_application_scope_takes_the_place_of_the_one_before() -> None:
    team = ClaimSetEntity("team", ("team_id",))
    extractor = ClaimExtractor([ClaimSetEntity("company", ("company_id",)), team])
    replacement = ClaimSetEntity("company", ("company_name",))

    extractor.add_claim_set(replacement)

    assert extractor.get_claim_sets()[-2:] == (replacement, team)


@pytest.mark.parametrize("scope", ["profile", "email", "address", "phone"])
def test_a_set_for_a_scope_the_protocol_defines_is_refused_by_name(scope: str) -> None:
    extractor = ClaimExtractor()

    with pytest.raises(InvalidArgumentError, match=scope):
        extractor.add_claim_set(ClaimSetEntity(scope, ("x",)))


def test_a_set_for_a_scope_the_protocol_defines_is_refused_when_built_with_it() -> None:
    with pytest.raises(InvalidArgumentError, match=r"email"):
        _ = ClaimExtractor([ClaimSetEntity("email", ("x",))])


def test_a_refused_set_reveals_nothing_in_place_of_the_protocol_claims() -> None:
    extractor = ClaimExtractor()
    with pytest.raises(InvalidArgumentError, match=r"email"):
        extractor.add_claim_set(ClaimSetEntity("email", ("x",)))

    revealed = extractor.extract(("email",), {"email": "alice@example.com", "x": "leaked"})

    assert revealed == {"email": "alice@example.com"}


def test_it_reveals_only_the_claims_the_granted_scopes_name() -> None:
    claims = {"email": "alice@example.com", "email_verified": True, "name": "Alice"}

    revealed = ClaimExtractor().extract(("openid", "email"), claims)

    assert revealed == {"email": "alice@example.com", "email_verified": True}


def test_a_claim_the_user_does_not_hold_is_left_out() -> None:
    revealed = ClaimExtractor().extract(("profile",), {"name": "Alice", "locale": "en-GB"})

    assert revealed == {"name": "Alice", "locale": "en-GB"}


def test_scopes_with_no_set_reveal_nothing() -> None:
    claims = {"email": "alice@example.com", "name": "Alice"}

    assert ClaimExtractor().extract(("openid", "read"), claims) == {}


def test_a_scope_of_the_applications_own_reveals_its_claims() -> None:
    extractor = ClaimExtractor([ClaimSetEntity("company", ("company_id",))])
    claims = {"company_id": "acme", "email": "alice@example.com"}

    assert extractor.extract(("openid", "company"), claims) == {"company_id": "acme"}


def test_a_claim_two_granted_scopes_name_is_revealed_once_beside_the_rest() -> None:
    extractor = ClaimExtractor([ClaimSetEntity("contact", ("email", "phone_number"))])
    claims = {"email": "alice@example.com", "email_verified": True, "phone_number": "+1 555 0100"}

    revealed = extractor.extract(("email", "contact"), claims)

    assert revealed == {
        "email": "alice@example.com",
        "email_verified": True,
        "phone_number": "+1 555 0100",
    }
