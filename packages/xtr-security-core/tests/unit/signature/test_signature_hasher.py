"""The signature hasher signs and checks hashes for users and expiry times."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import Enum
from typing import final

import pytest
from xtr_clock import MockClock

from xtr_security_core.exception import (
    ExpiredSignatureError,
    InvalidArgumentError,
    InvalidSignatureError,
)
from xtr_security_core.signature import SignatureHasher
from xtr_security_core.user import InMemoryUser

_NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
_NOW_TS = int(_NOW.timestamp())
_EXPIRES = _NOW_TS + 600


class _Tier(Enum):
    FREE = "free"
    PAID = "paid"


@final
@dataclass(frozen=True, slots=True)
class _ProfiledUser:
    """A user carrying the property shapes the hasher has to render."""

    identifier: str
    member_since: date = date(2020, 1, 1)
    tier: _Tier = _Tier.FREE
    payload: dict[str, int] = field(default_factory=dict)

    def get_user_identifier(self) -> str:
        return self.identifier

    def get_roles(self) -> tuple[str, ...]:
        return ()


def _hasher(properties: tuple[str, ...] = ("password",)) -> SignatureHasher:
    return SignatureHasher(properties, "secret", clock=MockClock(_NOW))


def _user(password: str) -> InMemoryUser:
    return InMemoryUser("alice", password=password, roles=["ROLE_USER"])


def test_a_computed_hash_is_accepted_for_the_identifier() -> None:
    hasher = _hasher()
    issued = hasher.compute_signature_hash(_user("hashed"), _EXPIRES)

    hasher.accept_signature_hash("alice", _EXPIRES, issued)


def test_a_computed_hash_is_verified_against_the_user() -> None:
    hasher = _hasher()
    issued = hasher.compute_signature_hash(_user("hashed"), _EXPIRES)

    hasher.verify_signature_hash(_user("hashed"), _EXPIRES, issued)


def test_a_hash_with_no_covered_properties_still_verifies() -> None:
    hasher = _hasher(())
    issued = hasher.compute_signature_hash(_user("hashed"), _EXPIRES)

    hasher.verify_signature_hash(_user("hashed"), _EXPIRES, issued)


def test_a_user_without_a_password_value_still_hashes() -> None:
    hasher = _hasher()
    issued = hasher.compute_signature_hash(InMemoryUser("alice"), _EXPIRES)

    hasher.verify_signature_hash(InMemoryUser("alice"), _EXPIRES, issued)


def test_an_expired_hash_is_refused_before_the_user_is_loaded() -> None:
    hasher = _hasher()
    issued = hasher.compute_signature_hash(_user("hashed"), _NOW_TS - 1)

    with pytest.raises(ExpiredSignatureError, match="expired"):
        hasher.accept_signature_hash("alice", _NOW_TS - 1, issued)


def test_an_expired_hash_is_refused_on_verify_too() -> None:
    hasher = _hasher()
    issued = hasher.compute_signature_hash(_user("hashed"), _NOW_TS - 1)

    with pytest.raises(ExpiredSignatureError, match="expired"):
        hasher.verify_signature_hash(_user("hashed"), _NOW_TS - 1, issued)


def test_a_hash_for_another_user_is_refused() -> None:
    issued = _hasher().compute_signature_hash(_user("hashed"), _EXPIRES)

    with pytest.raises(InvalidSignatureError):
        _hasher().accept_signature_hash("bob", _EXPIRES, issued)


def test_a_changed_property_invalidates_the_hash() -> None:
    hasher = _hasher()
    issued = hasher.compute_signature_hash(_user("old"), _EXPIRES)

    with pytest.raises(InvalidSignatureError):
        hasher.verify_signature_hash(_user("new"), _EXPIRES, issued)


def test_a_changed_flag_property_invalidates_the_hash() -> None:
    hasher = _hasher(("enabled",))
    issued = hasher.compute_signature_hash(InMemoryUser("alice", enabled=True), _EXPIRES)

    with pytest.raises(InvalidSignatureError):
        hasher.verify_signature_hash(InMemoryUser("alice", enabled=False), _EXPIRES, issued)


def test_a_changed_datetime_property_invalidates_the_hash() -> None:
    hasher = _hasher(("member_since",))
    issued = hasher.compute_signature_hash(_ProfiledUser("alice"), _EXPIRES)

    with pytest.raises(InvalidSignatureError):
        hasher.verify_signature_hash(
            _ProfiledUser("alice", member_since=date(2021, 1, 1)),
            _EXPIRES,
            issued,
        )


def test_a_changed_enum_property_invalidates_the_hash() -> None:
    hasher = _hasher(("tier",))
    issued = hasher.compute_signature_hash(_ProfiledUser("alice"), _EXPIRES)

    with pytest.raises(InvalidSignatureError):
        hasher.verify_signature_hash(_ProfiledUser("alice", tier=_Tier.PAID), _EXPIRES, issued)


def test_a_property_the_hash_cannot_render_is_refused() -> None:
    hasher = _hasher(("payload",))

    with pytest.raises(InvalidArgumentError, match="cast to a string"):
        _ = hasher.compute_signature_hash(_ProfiledUser("alice"), _EXPIRES)


def test_a_tampered_hash_is_refused() -> None:
    issued = _hasher().compute_signature_hash(_user("hashed"), _EXPIRES)
    tampered = issued[:-1] + ("A" if issued[-1] != "A" else "B")

    with pytest.raises(InvalidSignatureError):
        _hasher().accept_signature_hash("alice", _EXPIRES, tampered)


def test_a_truncated_hash_is_refused_on_verify() -> None:
    with pytest.raises(InvalidSignatureError):
        _hasher().verify_signature_hash(_user("hashed"), _EXPIRES, "too-short")


def test_a_hash_with_characters_outside_the_alphabet_is_refused() -> None:
    with pytest.raises(InvalidSignatureError):
        _hasher().accept_signature_hash("alice", _EXPIRES, "not-a-valid-hash-é")


def test_the_parameters_are_bound_into_the_hash() -> None:
    hasher = _hasher()
    issued = hasher.compute_signature_hash(_user("hashed"), _EXPIRES, {"channel": "web"})

    hasher.accept_signature_hash("alice", _EXPIRES, issued, {"channel": "web"})


def test_a_hash_without_its_parameters_is_refused() -> None:
    hasher = _hasher()
    issued = hasher.compute_signature_hash(_user("hashed"), _EXPIRES, {"channel": "web"})

    with pytest.raises(InvalidSignatureError):
        hasher.accept_signature_hash("alice", _EXPIRES, issued)


def test_the_parameter_order_does_not_change_the_hash() -> None:
    hasher = _hasher()

    first = hasher.compute_signature_hash(_user("hashed"), _EXPIRES, {"a": "1", "b": "2"})
    second = hasher.compute_signature_hash(_user("hashed"), _EXPIRES, {"b": "2", "a": "1"})

    assert first == second


def test_the_old_secret_still_verifies_after_a_rotation() -> None:
    retired = SignatureHasher(("password",), "old-secret", clock=MockClock(_NOW))
    rotated = SignatureHasher(("password",), ["new-secret", "old-secret"], clock=MockClock(_NOW))
    issued = retired.compute_signature_hash(_user("hashed"), _EXPIRES)

    rotated.verify_signature_hash(_user("hashed"), _EXPIRES, issued)


def test_a_hash_from_a_retired_secret_is_refused() -> None:
    retired = SignatureHasher(("password",), "old-secret", clock=MockClock(_NOW))
    rotated = SignatureHasher(("password",), ["new-secret"], clock=MockClock(_NOW))
    issued = retired.compute_signature_hash(_user("hashed"), _EXPIRES)

    with pytest.raises(InvalidSignatureError):
        rotated.verify_signature_hash(_user("hashed"), _EXPIRES, issued)


def test_an_empty_secret_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="secret"):
        _ = SignatureHasher(("password",), "")


def test_an_empty_secret_in_the_rotation_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="secret"):
        _ = SignatureHasher(("password",), ["secret", ""])


def test_a_secret_sequence_with_no_entries_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="secret"):
        _ = SignatureHasher(("password",), [])


def test_it_reads_the_system_clock_by_default() -> None:
    hasher = SignatureHasher(("password",), "secret")
    expires = int(datetime.now(UTC).timestamp()) + 10
    issued = hasher.compute_signature_hash(_user("hashed"), expires)

    hasher.verify_signature_hash(_user("hashed"), expires, issued)
