"""The loaded-token value object judges its times with the precedence of the reference."""

from __future__ import annotations

from xtr_clock import MockClock

from xtr_security_jwt.signature.loaded_jws import LoadedJws


def _clock() -> MockClock:
    return MockClock("2024-01-01 00:00:00")


def test_a_token_with_valid_times_is_verified() -> None:
    now = int(_clock().now().timestamp())
    loaded = LoadedJws({"iat": now, "exp": now + 100}, _clock(), is_verified=True)

    assert loaded.is_verified() is True
    assert loaded.is_invalid() is False
    assert loaded.is_expired() is False


def test_a_missing_expiry_is_invalid() -> None:
    now = int(_clock().now().timestamp())
    loaded = LoadedJws({"iat": now}, _clock(), is_verified=True)

    assert loaded.is_invalid() is True


def test_a_non_numeric_expiry_is_invalid() -> None:
    loaded = LoadedJws({"exp": "soon"}, _clock(), is_verified=True)

    assert loaded.is_invalid() is True


def test_a_past_expiry_is_expired() -> None:
    now = int(_clock().now().timestamp())
    loaded = LoadedJws({"iat": now - 200, "exp": now - 100}, _clock(), is_verified=True)

    assert loaded.is_expired() is True


def test_a_future_issued_at_is_invalid_overriding_a_good_signature() -> None:
    now = int(_clock().now().timestamp())
    loaded = LoadedJws({"iat": now + 100, "exp": now + 200}, _clock(), is_verified=True)

    assert loaded.is_invalid() is True
    assert loaded.is_verified() is True


def test_clock_skew_widens_the_expiry_window() -> None:
    now = int(_clock().now().timestamp())
    loaded = LoadedJws(
        {"iat": now, "exp": now - 5},
        _clock(),
        is_verified=True,
        clock_skew=10,
    )

    assert loaded.is_expired() is False


def test_allowing_no_expiration_skips_the_time_check() -> None:
    loaded = LoadedJws({}, _clock(), is_verified=True, should_check_expiration=False)

    assert loaded.is_invalid() is False
    assert loaded.is_expired() is False


def test_expiry_is_re_judged_as_time_passes() -> None:
    clock = _clock()
    now = int(clock.now().timestamp())
    loaded = LoadedJws({"iat": now, "exp": now + 50}, clock, is_verified=True)

    assert loaded.is_expired() is False
    clock.sleep(100)
    assert loaded.is_expired() is True


def test_it_returns_its_payload_and_header() -> None:
    now = int(_clock().now().timestamp())
    loaded = LoadedJws(
        {"iat": now, "exp": now + 10, "sub": "ada"},
        _clock(),
        is_verified=True,
        header={"alg": "RS256"},
    )

    assert loaded.get_payload()["sub"] == "ada"
    assert loaded.get_header() == {"alg": "RS256"}
