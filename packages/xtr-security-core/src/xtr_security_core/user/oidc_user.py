"""The user an OpenID Connect provider's claims describe."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from math import isfinite
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, Self, cast

from typing_extensions import override

from xtr_security_core.exception import InvalidArgumentError

from .user_interface import UserInterface

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = ["OidcUser"]

#: The claims mapped onto a string argument.
_STRING_CLAIMS: Final = frozenset(
    {
        "user_identifier",
        "sub",
        "name",
        "given_name",
        "family_name",
        "middle_name",
        "nickname",
        "preferred_username",
        "profile",
        "picture",
        "website",
        "email",
        "gender",
        "birthdate",
        "zoneinfo",
        "locale",
        "phone_number",
    },
)

#: The claims mapped onto a boolean argument.
_BOOLEAN_CLAIMS: Final = ("email_verified", "phone_number_verified")

#: The spellings a boolean claim is read from, lower-cased.
_TRUE_VALUES: Final = frozenset({"1", "true", "on", "yes"})
_FALSE_VALUES: Final = frozenset({"0", "false", "off", "no", ""})


class OidcUser(UserInterface):
    """The user the security workflows with an OpenID Connect server settle on.

    It carries the standard claims
    (https://openid.net/specs/openid-connect-core-1_0.html#StandardClaims) as
    typed fields and keeps every other claim as an additional claim. The ``sub``
    claim is required; the user is identified by ``user_identifier`` when given,
    by ``sub`` otherwise.

    Neither OIDC nor OAuth has a notion of role: the user holds ``ROLE_USER``
    unless built with other roles — by a provider mapping claims onto roles,
    say.
    """

    __slots__: tuple[str, ...] = (
        "_additional_claims",
        "_address",
        "_birthdate",
        "_email",
        "_email_verified",
        "_family_name",
        "_gender",
        "_given_name",
        "_locale",
        "_middle_name",
        "_name",
        "_nickname",
        "_phone_number",
        "_phone_number_verified",
        "_picture",
        "_preferred_username",
        "_profile",
        "_roles",
        "_sub",
        "_updated_at",
        "_user_identifier",
        "_website",
        "_zoneinfo",
    )

    _user_identifier: str | None
    _roles: tuple[str, ...]
    _sub: str
    _name: str | None
    _given_name: str | None
    _family_name: str | None
    _middle_name: str | None
    _nickname: str | None
    _preferred_username: str | None
    _profile: str | None
    _picture: str | None
    _website: str | None
    _email: str | None
    _email_verified: bool | None
    _gender: str | None
    _birthdate: str | None
    _zoneinfo: str | None
    _locale: str | None
    _phone_number: str | None
    _phone_number_verified: bool | None
    _address: Mapping[str, object] | None
    _updated_at: datetime | None
    _additional_claims: dict[str, object]

    def __init__(  # noqa: PLR0913, PLR0917 -- one parameter per standard claim, in its order
        self,
        user_identifier: str | None = None,
        roles: Sequence[str] = ("ROLE_USER",),
        sub: str | None = None,
        name: str | None = None,
        given_name: str | None = None,
        family_name: str | None = None,
        middle_name: str | None = None,
        nickname: str | None = None,
        preferred_username: str | None = None,
        profile: str | None = None,
        picture: str | None = None,
        website: str | None = None,
        email: str | None = None,
        email_verified: bool | None = None,
        gender: str | None = None,
        birthdate: str | None = None,
        zoneinfo: str | None = None,
        locale: str | None = None,
        phone_number: str | None = None,
        phone_number_verified: bool | None = None,
        address: Mapping[str, object] | None = None,
        updated_at: datetime | None = None,
        **additional_claims: object,
    ) -> None:
        """Record the standard claims, and keep every other one as an additional claim.

        An ``additional_claims`` keyword, when given, is taken as the
        additional claims themselves rather than as one of them.

        Raises:
            InvalidArgumentError: When the ``sub`` claim is missing or empty.
        """
        if sub is None or sub == "":
            raise InvalidArgumentError('The "sub" claim cannot be empty.')
        self._user_identifier = user_identifier
        self._roles = tuple(roles)
        self._sub = sub
        self._name = name
        self._given_name = given_name
        self._family_name = family_name
        self._middle_name = middle_name
        self._nickname = nickname
        self._preferred_username = preferred_username
        self._profile = profile
        self._picture = picture
        self._website = website
        self._email = email
        self._email_verified = email_verified
        self._gender = gender
        self._birthdate = birthdate
        self._zoneinfo = zoneinfo
        self._locale = locale
        self._phone_number = phone_number
        self._phone_number_verified = phone_number_verified
        self._address = address
        self._updated_at = updated_at
        nested = additional_claims.get("additional_claims")
        self._additional_claims = (
            dict(cast("Mapping[str, object]", nested))
            if "additional_claims" in additional_claims and isinstance(nested, dict)
            else dict(additional_claims)
        )

    @classmethod
    def from_claims(cls, claims: Mapping[str, object]) -> Self:
        """Build a user from the claims returned by an OIDC provider.

        Claim names are snake-cased onto the constructor arguments, and the
        ones matching no argument become additional claims. Every claim is
        mapped this way, so a ``roles`` claim does grant the roles it holds:
        only pass claims you decided to trust, either because you verified
        where they come from or because you mapped them yourself. Claims whose
        value does not fit the type of their argument are dropped, so that a
        misbehaving provider cannot break authentication with a type error.

        Raises:
            InvalidArgumentError: When the ``sub`` claim is missing or empty.
        """
        mapped: dict[str, object] = {}
        for claim, value in claims.items():
            if value is None or value == "":
                continue
            name = _snake_case(claim)
            fitted = _fit(name, value)
            if fitted is not _DROPPED:
                mapped[name] = fitted
        roles = mapped.pop("roles", None)
        address = mapped.pop("address", None)
        updated_at = mapped.pop("updated_at", None)
        return cls(
            _pop_str(mapped, "user_identifier"),
            cast("tuple[str, ...]", roles) if isinstance(roles, tuple) else ("ROLE_USER",),
            _pop_str(mapped, "sub"),
            _pop_str(mapped, "name"),
            _pop_str(mapped, "given_name"),
            _pop_str(mapped, "family_name"),
            _pop_str(mapped, "middle_name"),
            _pop_str(mapped, "nickname"),
            _pop_str(mapped, "preferred_username"),
            _pop_str(mapped, "profile"),
            _pop_str(mapped, "picture"),
            _pop_str(mapped, "website"),
            _pop_str(mapped, "email"),
            _pop_bool(mapped, "email_verified"),
            _pop_str(mapped, "gender"),
            _pop_str(mapped, "birthdate"),
            _pop_str(mapped, "zoneinfo"),
            _pop_str(mapped, "locale"),
            _pop_str(mapped, "phone_number"),
            _pop_bool(mapped, "phone_number_verified"),
            cast("Mapping[str, object]", address) if isinstance(address, dict) else None,
            updated_at if isinstance(updated_at, datetime) else None,
            **mapped,
        )

    @override
    def get_roles(self) -> Sequence[str]:
        """Return the roles granted to this user; ``ROLE_USER`` unless built otherwise."""
        return self._roles

    @override
    def get_user_identifier(self) -> str:
        """Return ``user_identifier`` when given, the ``sub`` claim otherwise."""
        return self._user_identifier if self._user_identifier is not None else self._sub

    def get_sub(self) -> str:
        """Return the ``sub`` claim."""
        return self._sub

    def get_name(self) -> str | None:
        """Return the ``name`` claim."""
        return self._name

    def get_given_name(self) -> str | None:
        """Return the ``given_name`` claim."""
        return self._given_name

    def get_family_name(self) -> str | None:
        """Return the ``family_name`` claim."""
        return self._family_name

    def get_middle_name(self) -> str | None:
        """Return the ``middle_name`` claim."""
        return self._middle_name

    def get_nickname(self) -> str | None:
        """Return the ``nickname`` claim."""
        return self._nickname

    def get_preferred_username(self) -> str | None:
        """Return the ``preferred_username`` claim."""
        return self._preferred_username

    def get_profile(self) -> str | None:
        """Return the ``profile`` claim."""
        return self._profile

    def get_picture(self) -> str | None:
        """Return the ``picture`` claim."""
        return self._picture

    def get_website(self) -> str | None:
        """Return the ``website`` claim."""
        return self._website

    def get_email(self) -> str | None:
        """Return the ``email`` claim."""
        return self._email

    def get_email_verified(self) -> bool | None:
        """Return the ``email_verified`` claim."""
        return self._email_verified

    def get_gender(self) -> str | None:
        """Return the ``gender`` claim."""
        return self._gender

    def get_birthdate(self) -> str | None:
        """Return the ``birthdate`` claim."""
        return self._birthdate

    def get_zoneinfo(self) -> str | None:
        """Return the ``zoneinfo`` claim."""
        return self._zoneinfo

    def get_locale(self) -> str | None:
        """Return the ``locale`` claim."""
        return self._locale

    def get_phone_number(self) -> str | None:
        """Return the ``phone_number`` claim."""
        return self._phone_number

    def get_phone_number_verified(self) -> bool | None:
        """Return the ``phone_number_verified`` claim."""
        return self._phone_number_verified

    def get_address(self) -> Mapping[str, object] | None:
        """Return the ``address`` claim."""
        return self._address

    def get_updated_at(self) -> datetime | None:
        """Return the ``updated_at`` claim."""
        return self._updated_at

    def get_additional_claims(self) -> Mapping[str, object]:
        """Return every claim that is not a standard one, read-only."""
        return MappingProxyType(self._additional_claims)


#: The marker a claim whose value does not fit its argument is fitted to.
_DROPPED: Final = object()


def _pop_str(mapped: dict[str, object], name: str) -> str | None:
    """Take the fitted string claim ``name`` out of ``mapped``, if there is one."""
    value = mapped.pop(name, None)
    return value if isinstance(value, str) else None


def _pop_bool(mapped: dict[str, object], name: str) -> bool | None:
    """Take the fitted boolean claim ``name`` out of ``mapped``, if there is one."""
    value = mapped.pop(name, None)
    return value if isinstance(value, bool) else None


def _snake_case(claim: str) -> str:
    """Snake-case a claim name: split on case changes and on anything not a letter or digit."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "_", claim)
    return "_".join(part for part in re.split(r"[^A-Za-z0-9]+", spaced) if part).lower()


def _fit(name: str, value: object) -> object:  # noqa: PLR0911 -- one return per argument type
    """Fit ``value`` to the type of the argument ``name``, or return :data:`_DROPPED`."""
    if name == "roles":
        if isinstance(value, (list, tuple)):
            return tuple(str(role) for role in cast("Sequence[object]", value))
        return _DROPPED
    if name in {"address", "additional_claims"}:
        return dict(cast("Mapping[str, object]", value)) if isinstance(value, dict) else _DROPPED
    if name in _BOOLEAN_CLAIMS:
        return _to_bool(value)
    if name == "updated_at":
        if isinstance(value, bool) or not _is_numeric(value):
            return _DROPPED
        return datetime.fromtimestamp(int(float(cast("str | float", value))), tz=UTC)
    if name in _STRING_CLAIMS:
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        return _DROPPED
    return value


def _to_bool(value: object) -> object:
    """Read a recognisable boolean, or return :data:`_DROPPED` for anything else.

    A string ``"false"`` would read as true were it simply truth-tested, so
    only a recognisable spelling is kept.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if value in {0, 1}:
            return bool(value)
        return _DROPPED
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in _TRUE_VALUES:
            return True
        if lowered in _FALSE_VALUES:
            return False
    return _DROPPED


def _is_numeric(value: object) -> bool:
    """Tell whether ``value`` is a finite number, or a string spelling one."""
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return isfinite(value)
    if isinstance(value, str):
        try:
            number = float(value)
        except ValueError:
            return False
        return isfinite(number)
    return False
