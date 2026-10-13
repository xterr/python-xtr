"""The authentication methods carry their RFC 8176 values."""

from __future__ import annotations

from xtr_security_core.authentication import AuthenticationMethod


def test_the_methods_carry_their_registered_values() -> None:
    assert {
        AuthenticationMethod.FACE,
        AuthenticationMethod.FINGERPRINT,
        AuthenticationMethod.GEOLOCATION,
        AuthenticationMethod.HARDWARE_KEY,
        AuthenticationMethod.IRIS,
        AuthenticationMethod.KNOWLEDGE_BASED,
        AuthenticationMethod.MULTIPLE_CHANNELS,
        AuthenticationMethod.MULTIPLE_FACTORS,
        AuthenticationMethod.ONE_TIME_PASSWORD,
        AuthenticationMethod.PIN,
        AuthenticationMethod.PASSWORD,
        AuthenticationMethod.RISK_BASED,
        AuthenticationMethod.RETINA,
        AuthenticationMethod.SMART_CARD,
        AuthenticationMethod.SMS,
        AuthenticationMethod.SOFTWARE_KEY,
        AuthenticationMethod.TELEPHONE_CALL,
        AuthenticationMethod.USER_PRESENCE,
        AuthenticationMethod.VOICE,
        AuthenticationMethod.WINDOWS_INTEGRATED,
    } == {
        "face",
        "fpt",
        "geo",
        "hwk",
        "iris",
        "kba",
        "mca",
        "mfa",
        "otp",
        "pin",
        "pwd",
        "rba",
        "retina",
        "sc",
        "sms",
        "swk",
        "tel",
        "user",
        "vbm",
        "wia",
    }


def test_an_unstated_method_is_not_a_registered_value() -> None:
    assert AuthenticationMethod.UNSPECIFIED == "*"
