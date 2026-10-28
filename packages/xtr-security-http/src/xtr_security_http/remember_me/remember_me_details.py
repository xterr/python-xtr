"""The value a remember-me cookie carries, and the shape it must keep.

A remember-me cookie's value is one string with a fixed layout: an empty
field, the base64 of the user's identifier, the expiry as a Unix timestamp,
and the handler's own value — each field separated from the next by a colon.
The empty first field is part of the format, not a mistake: the value begins
with the separator, so the fields always split at the same places whatever
the identifier carries. The identifier is base64-encoded in the URL-safe
alphabet — ``+``, ``/`` and ``=`` written as ``-``, ``_`` and ``~`` — because
the identifier itself may contain the separator; the other fields are assumed
not to, and the handlers keep to that assumption by construction.
"""

from __future__ import annotations

import base64
import binascii
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_security_core.exception import AuthenticationError

if TYPE_CHECKING:
    from xtr_security_core.authentication.remember_me.persistent_token import PersistentToken

__all__ = ["RememberMeDetails"]

#: The character one field of the cookie value ends with and the next begins
#: after. The value starts with it, so the first field is always empty.
_COOKIE_DELIMITER = ":"

#: The URL-safe spelling of the base64 alphabet: the characters a cookie value
#: may not carry, written as the ones it may.
_ENCODE_ALPHABET = str.maketrans("+/=", "-_~")

#: The standard spelling back again, for reading an identifier out of a cookie.
_DECODE_ALPHABET = str.maketrans("-_~", "+/=")

#: How many fields the cookie's value carries: the empty one, the encoded
#: identifier, the expiry and the handler's own value.
_FIELD_COUNT = 4


@final
class RememberMeDetails:
    """Who a remember-me cookie remembers, until when, and by what value.

    The cookie's whole content in one value object: the identifier of the
    user it remembers, the expiry the value stops counting at, and the value
    the handler that issued it can check. The serialization is the format
    itself — :meth:`from_raw_cookie` reads what :meth:`__str__` writes, so a
    cookie written by one handler is read by the same one, and the layout is
    pinned rather than implied by a serializer's choices.
    """

    __slots__ = ("_expires", "_user_identifier", "_value")

    _user_identifier: str
    _expires: int
    _value: str

    def __init__(self, user_identifier: str, expires: int, value: str) -> None:
        """Record the identifier, the expiry and the handler's own value."""
        self._user_identifier = user_identifier
        self._expires = expires
        self._value = value

    @classmethod
    def from_raw_cookie(cls, raw_cookie: str) -> RememberMeDetails:
        """Read a cookie's value back into the details it was written from.

        A value carrying no separator at all was written base64-encoded as a
        whole, so it is decoded first — the layout then continues as always.
        A value that does not split into the four fields, whose identifier is
        not base64 in the URL-safe alphabet, or whose expiry is not a number,
        is not a cookie this flow issued, and is refused as such.

        Args:
            raw_cookie: The cookie's value, exactly as the request carried it.

        Returns:
            The details the value was written from.

        Raises:
            AuthenticationError: When the value is not a remember-me cookie
                this flow could have written.
        """
        raw = raw_cookie
        if _COOKIE_DELIMITER not in raw:
            try:
                raw = base64.b64decode(raw).decode("utf-8")
            except (binascii.Error, UnicodeDecodeError):
                raise AuthenticationError("The cookie contains invalid data.") from None
        fields = raw.split(_COOKIE_DELIMITER, 3)
        if len(fields) != _FIELD_COUNT:
            raise AuthenticationError("The cookie contains invalid data.")
        try:
            user_identifier = base64.b64decode(
                fields[1].translate(_DECODE_ALPHABET),
                validate=True,
            ).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            raise AuthenticationError(
                "The user identifier contains a character from outside the base64 alphabet.",
            ) from None
        try:
            expires = int(fields[2])
        except ValueError:
            raise AuthenticationError("The cookie contains invalid data.") from None
        return cls(user_identifier, expires, fields[3])

    @classmethod
    def from_persistent_token(cls, token: PersistentToken, expires: int) -> RememberMeDetails:
        """Write a persistent token's series and value into a cookie's value.

        The persistent handler's value is the series and the token value it
        expects next, separated the way the cookie's own fields are — so the
        one separator layout serves both, and the handler reading the cookie
        back finds its two parts where it wrote them.

        Args:
            token: The persistent token a series stored.
            expires: The expiry the cookie stops counting at, as a Unix
                timestamp.

        Returns:
            The details for the cookie that hands the token to the caller's
            next request.
        """
        return cls(
            token.get_user_identifier(),
            expires,
            f"{token.get_series()}{_COOKIE_DELIMITER}{token.get_token_value()}",
        )

    def with_value(self, value: str) -> RememberMeDetails:
        """Return details carrying ``value`` in place of this one's own.

        The rotation writes a new value into details it already read the rest
        of — the identifier and the expiry stand, only the value moves.
        """
        return RememberMeDetails(self._user_identifier, self._expires, value)

    def get_user_identifier(self) -> str:
        """Return the identifier of the user this cookie remembers."""
        return self._user_identifier

    def get_expires(self) -> int:
        """Return the expiry this cookie stops counting at, as a Unix timestamp."""
        return self._expires

    def get_value(self) -> str:
        """Return the value the handler that issued this cookie checks."""
        return self._value

    @override
    def __str__(self) -> str:
        """Return the cookie's value: the layout every handler writes.

        The identifier is encoded in the URL-safe base64 alphabet because it
        may carry the separator; the other fields are written as they are.
        """
        encoded = (
            base64.b64encode(self._user_identifier.encode("utf-8"))
            .decode("ascii")
            .translate(_ENCODE_ALPHABET)
        )
        return _COOKIE_DELIMITER.join(("", encoded, str(self._expires), self._value))
