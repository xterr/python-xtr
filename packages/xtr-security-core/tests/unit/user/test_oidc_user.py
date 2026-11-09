"""The OIDC user carries the standard claims, and builds itself from a claims mapping."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from xtr_security_core.exception import InvalidArgumentError
from xtr_security_core.user import OidcUser, UserInterface


def test_it_inherits_the_user_interface() -> None:
    assert UserInterface in OidcUser.__mro__


def test_it_is_identified_by_the_sub_and_holds_role_user_by_default() -> None:
    user = OidcUser(sub="alice")

    assert user.get_user_identifier() == "alice"
    assert user.get_sub() == "alice"
    assert user.get_roles() == ("ROLE_USER",)


def test_a_given_user_identifier_wins_over_the_sub() -> None:
    user = OidcUser(user_identifier="alice@example.test", sub="alice")

    assert user.get_user_identifier() == "alice@example.test"


def test_custom_roles() -> None:
    assert OidcUser(sub="alice", roles=["ROLE_ADMIN"]).get_roles() == ("ROLE_ADMIN",)


@pytest.mark.parametrize("sub", [None, ""])
def test_a_missing_or_empty_sub_is_refused(sub: str | None) -> None:
    with pytest.raises(InvalidArgumentError, match='The "sub" claim cannot be empty'):
        _ = OidcUser(sub=sub)


def test_it_carries_every_standard_claim() -> None:
    updated_at = datetime(2026, 1, 1, tzinfo=UTC)
    user = OidcUser(
        sub="alice",
        name="Alice Liddell",
        given_name="Alice",
        family_name="Liddell",
        middle_name="Pleasance",
        nickname="Al",
        preferred_username="alice",
        profile="https://example.test/alice",
        picture="https://example.test/alice.png",
        website="https://alice.example.test",
        email="alice@example.test",
        email_verified=True,
        gender="female",
        birthdate="1852-05-04",
        zoneinfo="Europe/London",
        locale="en-GB",
        phone_number="+44 1",
        phone_number_verified=False,
        address={"country": "UK"},
        updated_at=updated_at,
    )

    assert (
        user.get_name(),
        user.get_given_name(),
        user.get_family_name(),
        user.get_middle_name(),
        user.get_nickname(),
        user.get_preferred_username(),
        user.get_profile(),
        user.get_picture(),
        user.get_website(),
        user.get_email(),
        user.get_email_verified(),
        user.get_gender(),
        user.get_birthdate(),
        user.get_zoneinfo(),
        user.get_locale(),
        user.get_phone_number(),
        user.get_phone_number_verified(),
        user.get_address(),
        user.get_updated_at(),
    ) == (
        "Alice Liddell",
        "Alice",
        "Liddell",
        "Pleasance",
        "Al",
        "alice",
        "https://example.test/alice",
        "https://example.test/alice.png",
        "https://alice.example.test",
        "alice@example.test",
        True,
        "female",
        "1852-05-04",
        "Europe/London",
        "en-GB",
        "+44 1",
        False,
        {"country": "UK"},
        updated_at,
    )


def test_other_keywords_become_additional_claims() -> None:
    user = OidcUser(sub="alice", tenant="acme", groups=["staff"])

    assert dict(user.get_additional_claims()) == {"tenant": "acme", "groups": ["staff"]}


def test_an_additional_claims_keyword_is_taken_as_the_claims_themselves() -> None:
    user = OidcUser(sub="alice", additional_claims={"tenant": "acme"})

    assert dict(user.get_additional_claims()) == {"tenant": "acme"}


def test_from_claims_maps_standard_claims_and_keeps_the_rest() -> None:
    user = OidcUser.from_claims(
        {
            "sub": "alice",
            "given_name": "Alice",
            "emailVerified": "true",
            "updated_at": 1_767_225_600,
            "tenant": "acme",
        },
    )

    assert user.get_given_name() == "Alice"
    assert user.get_email_verified() is True
    assert user.get_updated_at() == datetime(2026, 1, 1, tzinfo=UTC)
    assert dict(user.get_additional_claims()) == {"tenant": "acme"}


def test_from_claims_snake_cases_every_claim_name() -> None:
    user = OidcUser.from_claims({"sub": "alice", "family-name": "Liddell", "tenantId": "t1"})

    assert user.get_family_name() == "Liddell"
    assert dict(user.get_additional_claims()) == {"tenant_id": "t1"}


def test_from_claims_skips_empty_values() -> None:
    user = OidcUser.from_claims({"sub": "alice", "name": "", "email": None})

    assert user.get_name() is None
    assert user.get_email() is None


def test_from_claims_grants_the_roles_claim() -> None:
    user = OidcUser.from_claims({"sub": "alice", "roles": ["ROLE_ADMIN"]})

    assert user.get_roles() == ("ROLE_ADMIN",)


def test_from_claims_drops_values_that_do_not_fit_their_argument() -> None:
    user = OidcUser.from_claims(
        {
            "sub": "alice",
            "roles": "ROLE_ADMIN",
            "address": "somewhere",
            "name": ["not", "a", "string"],
            "updated_at": "yesterday",
            "email_verified": "maybe",
            "phone_number_verified": 2,
        },
    )

    assert user.get_roles() == ("ROLE_USER",)
    assert user.get_address() is None
    assert user.get_name() is None
    assert user.get_updated_at() is None
    assert user.get_email_verified() is None
    assert user.get_phone_number_verified() is None


def test_from_claims_reads_only_recognisable_booleans() -> None:
    falsy = OidcUser.from_claims({"sub": "alice", "email_verified": "false"})
    truthy = OidcUser.from_claims({"sub": "alice", "email_verified": 1})

    assert falsy.get_email_verified() is False
    assert truthy.get_email_verified() is True


def test_from_claims_reads_a_numeric_string_timestamp() -> None:
    user = OidcUser.from_claims({"sub": "alice", "updated_at": "1767225600"})

    assert user.get_updated_at() == datetime(2026, 1, 1, tzinfo=UTC)


def test_from_claims_turns_a_number_into_a_string_claim() -> None:
    user = OidcUser.from_claims({"sub": 42})

    assert user.get_sub() == "42"


def test_from_claims_needs_a_sub() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = OidcUser.from_claims({"email": "alice@example.test"})


def _every_claim() -> OidcUser:
    return OidcUser(
        user_identifier="alice@example.test",
        roles=("ROLE_USER", "ROLE_EDITOR"),
        sub="alice",
        name="Alice Liddell",
        given_name="Alice",
        family_name="Liddell",
        middle_name="Pleasance",
        nickname="Al",
        preferred_username="alice",
        profile="https://example.test/alice",
        picture="https://example.test/alice.png",
        website="https://alice.example.test",
        email="alice@example.test",
        email_verified=True,
        gender="female",
        birthdate="1852-05-04",
        zoneinfo="Europe/London",
        locale="en-GB",
        phone_number="+44 1",
        phone_number_verified=False,
        address={"country": "UK", "lines": ["1 Wonderland"]},
        updated_at=datetime(2026, 1, 1, 12, 30, tzinfo=UTC),
        additional_claims={"tenant": "acme", "groups": ["readers"]},
    )


def _claims_of(user: OidcUser) -> tuple[object, ...]:
    return (
        user.get_user_identifier(),
        tuple(user.get_roles()),
        user.get_sub(),
        user.get_name(),
        user.get_given_name(),
        user.get_family_name(),
        user.get_middle_name(),
        user.get_nickname(),
        user.get_preferred_username(),
        user.get_profile(),
        user.get_picture(),
        user.get_website(),
        user.get_email(),
        user.get_email_verified(),
        user.get_gender(),
        user.get_birthdate(),
        user.get_zoneinfo(),
        user.get_locale(),
        user.get_phone_number(),
        user.get_phone_number_verified(),
        user.get_address(),
        user.get_updated_at(),
        dict(user.get_additional_claims()),
    )


def test_it_is_rebuilt_from_a_session_with_every_claim_and_its_roles() -> None:
    user = _every_claim()

    rebuilt = OidcUser.from_session(user.to_session())

    assert _claims_of(rebuilt) == _claims_of(user)


def test_a_session_keeps_the_moment_it_was_updated_as_iso_8601() -> None:
    assert _every_claim().to_session()["updated_at"] == "2026-01-01T12:30:00+00:00"


def test_a_user_with_no_optional_claim_is_rebuilt_from_a_session() -> None:
    user = OidcUser(sub="alice")

    rebuilt = OidcUser.from_session(user.to_session())

    assert _claims_of(rebuilt) == _claims_of(user)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sub", ""),
        ("sub", None),
        ("roles", "ROLE_USER"),
        ("email", 1),
        ("email_verified", "yes"),
        ("address", "somewhere"),
        ("updated_at", "yesterday"),
        ("additional_claims", None),
    ],
)
def test_a_malformed_session_state_is_refused(field: str, value: object) -> None:
    state = {**_every_claim().to_session(), field: value}

    with pytest.raises(InvalidArgumentError):
        _ = OidcUser.from_session(state)
