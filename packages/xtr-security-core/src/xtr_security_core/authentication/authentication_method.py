"""The authentication methods a token can hold a proof of."""

from __future__ import annotations

from typing import Final, final

__all__ = ["AuthenticationMethod"]


@final
class AuthenticationMethod:
    """The authentication methods a token can hold a proof of, named as RFC 8176 registers them.

    They key the mapping
    :meth:`~xtr_security_core.authentication.token.token_interface.TokenInterface.get_authentication_proofs`
    returns, so that a trust resolver can require a specific one. The values are
    those of the OpenID Connect ``amr`` claim, which a provider may extend beyond
    this list — hence a set of names rather than a closed enumeration.

    See https://www.rfc-editor.org/rfc/rfc8176.html#section-2.
    """

    UNSPECIFIED: Final[str] = "*"
    """A proof whose method the authenticator did not state; not a registered value."""

    FACE: Final[str] = "face"
    """Facial recognition."""

    FINGERPRINT: Final[str] = "fpt"
    """Fingerprint biometric."""

    GEOLOCATION: Final[str] = "geo"
    """Use of geolocation information."""

    HARDWARE_KEY: Final[str] = "hwk"
    """Proof-of-possession of a hardware-secured key."""

    IRIS: Final[str] = "iris"
    """Iris scan biometric."""

    KNOWLEDGE_BASED: Final[str] = "kba"
    """Knowledge-based authentication."""

    MULTIPLE_CHANNELS: Final[str] = "mca"
    """Multiple-channel authentication, e.g. confirming a login over another channel."""

    MULTIPLE_FACTORS: Final[str] = "mfa"
    """Multiple-factor authentication, when the provider names no individual factor."""

    ONE_TIME_PASSWORD: Final[str] = "otp"  # noqa: S105 -- a registered method name, not a secret
    """One-time password, e.g. a TOTP."""

    PIN: Final[str] = "pin"
    """Personal identification number or pattern."""

    PASSWORD: Final[str] = "pwd"  # noqa: S105 -- a registered method name, not a secret
    """Password-based authentication."""

    RISK_BASED: Final[str] = "rba"
    """Risk-based authentication."""

    RETINA: Final[str] = "retina"
    """Retina scan biometric."""

    SMART_CARD: Final[str] = "sc"
    """Smart card."""

    SMS: Final[str] = "sms"
    """Confirmation by SMS text message."""

    SOFTWARE_KEY: Final[str] = "swk"
    """Proof-of-possession of a software-secured key."""

    TELEPHONE_CALL: Final[str] = "tel"
    """Confirmation by telephone call."""

    USER_PRESENCE: Final[str] = "user"
    """User presence test."""

    VOICE: Final[str] = "vbm"
    """Voice biometric."""

    WINDOWS_INTEGRATED: Final[str] = "wia"
    """Windows integrated authentication."""
