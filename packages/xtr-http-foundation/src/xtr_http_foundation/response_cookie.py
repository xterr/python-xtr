"""The header value that sets a cookie on a response, or clears one."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from urllib.parse import quote

from xtr_http_foundation.exception import InvalidArgumentError

__all__ = ["cleared_cookie_header_value", "cookie_header_value"]

# A name may carry these only per cent-encoded: the equals sign and the
# semicolon give a cookie its shape, the comma separates cookies from one
# another, and whitespace never survived a well-formed one.
_NAME_TRANSLATION = str.maketrans(
    {
        "=": "%3D",
        ",": "%2C",
        ";": "%3B",
        " ": "%20",
        "\t": "%09",
        "\r": "%0D",
        "\n": "%0A",
        "\v": "%0B",
        "\f": "%0C",
    }
)

# The characters a path or a domain may never carry: the separators of the
# attributes that follow. An equals sign is fine there — an attribute is
# itself written as name=value.
_ATTRIBUTE_SEPARATORS = frozenset(",; \t\r\n\v\f")

_SAMESITE_VALUES = ("lax", "none", "strict")

# A cleared cookie is dated a year and a second ago, so no clock that runs a
# little behind un-clears it.
_DELETED_AGO = timedelta(seconds=31536001)


def cookie_header_value(  # noqa: PLR0913 — a Set-Cookie header carries exactly these attributes, and the caller places them as one header's options.
    name: str,
    value: str,
    *,
    expires: datetime | None = None,
    path: str | None = "/",
    domain: str | None = None,
    secure: bool = False,
    httponly: bool = True,
    samesite: str | None = "lax",
) -> str:
    """Return the value a ``Set-Cookie`` header carries to set one cookie.

    A response sets a cookie by carrying this value, so the cookie is built
    where the response is, in the header it already knows how to place, and
    no response type of this library's own is dragged in for it.

    The value is per cent-encoded as it cannot sit in a header — a space, a
    slash, anything a separator could read as — and so is a name carrying the
    characters that give a cookie its shape. A value that is empty writes the
    cleared form instead: a browser keeps a cookie only while it is dated
    ahead, so the cookie is dated a year behind and ages out at once.

    Args:
        name: The cookie's name.
        value: The cookie's value; empty to clear the cookie.
        expires: When the cookie stops being kept. Written as both the
            ``expires`` a person reads and the ``Max-Age`` a client counts
            down, since a client honours only one of them and which one
            differs. A naive datetime is read as UTC. ``None`` for a cookie
            that lives for the session.
        path: The path the cookie is available under; the whole site by
            default, and an empty path is read the same way.
        domain: The domain the cookie is available to; every host that reads
            it when ``None``.
        secure: Whether the cookie travels only over a secure connection.
        httponly: Whether the cookie stays out of the scripts a page runs.
        samesite: Whether the cookie travels on cross-site requests —
            ``"lax"``, ``"strict"`` or ``"none"``, read without regard to
            case; ``None`` or ``""`` writes no attribute.

    Returns:
        The header value, ready for ``with_header("Set-Cookie", ...)``.

    Raises:
        InvalidArgumentError: When the name is empty or carries a reserved
            prefix without what the prefix asks for, when ``samesite`` is
            none of the three, or when the path or the domain carries the
            separators of the attributes that follow.
    """
    if not name:
        raise InvalidArgumentError("The cookie name cannot be empty.")

    samesite = _normalised_samesite(samesite)
    path = _validated_path(path)
    _validated_domain(domain)
    _validated_prefix(name, domain, path, secure)

    attributes = [f"path={path}"]
    if domain:
        attributes.append(f"domain={domain}")
    if secure:
        attributes.append("secure")
    if httponly:
        attributes.append("httponly")
    if samesite is not None:
        attributes.append(f"samesite={samesite}")

    return f"{name.translate(_NAME_TRANSLATION)}={_value_part(value, expires)}; " + "; ".join(
        attributes
    )


def cleared_cookie_header_value(  # noqa: PLR0913 — the attributes a cookie was set with, which the header that clears it must repeat.
    name: str,
    *,
    path: str | None = "/",
    domain: str | None = None,
    secure: bool = False,
    httponly: bool = True,
    samesite: str | None = "lax",
) -> str:
    """Return the value a ``Set-Cookie`` header carries to clear one cookie.

    A browser drops a cookie when the header that names it dates it behind
    now, so clearing is setting with the value emptied — and the path and
    the domain must be the ones the cookie was set with, because a browser
    tells cookies apart by all three.

    Args:
        name: The cookie's name, as it was set.
        path: The path the cookie was set under.
        domain: The domain the cookie was set to.
        secure: Whether the cookie was set to travel only over a secure
            connection.
        httponly: Whether the cookie was kept out of the scripts a page runs.
        samesite: The cross-site rule the cookie was set with.

    Returns:
        The header value, ready for ``with_header("Set-Cookie", ...)``.
    """
    return cookie_header_value(
        name,
        "",
        path=path,
        domain=domain,
        secure=secure,
        httponly=httponly,
        samesite=samesite,
    )


def _normalised_samesite(samesite: str | None) -> str | None:
    """Return ``samesite`` as the attribute writes it, or ``None`` for no attribute at all."""
    if samesite in (None, ""):
        return None

    normalised = samesite.lower()
    if normalised not in _SAMESITE_VALUES:
        raise InvalidArgumentError(
            f'"{normalised}" is not a samesite value: use "lax", "strict", "none" or None.'
        )

    return normalised


def _validated_path(path: str | None) -> str:
    """Return ``path`` as the attribute writes it: the whole site where nothing is said."""
    normalised = path or "/"
    if not _ATTRIBUTE_SEPARATORS.isdisjoint(normalised):
        raise InvalidArgumentError(
            f'The cookie path "{normalised}" contains characters a cookie attribute cannot carry.'
        )

    return normalised


def _validated_domain(domain: str | None) -> None:
    """Refuse a domain that cannot sit in an attribute."""
    if domain is not None and not _ATTRIBUTE_SEPARATORS.isdisjoint(domain):
        raise InvalidArgumentError(
            f'The cookie domain "{domain}" contains characters a cookie attribute cannot carry.'
        )


def _validated_prefix(name: str, domain: str | None, path: str, secure: bool) -> None:
    """Refuse a reserved name prefix without what the prefix asks a cookie to carry.

    A browser silently discards a cookie whose prefix promises more than its
    attributes deliver, so the builder refuses it here, where the reason can
    be read.
    """
    if not secure and name.startswith(("__Secure-", "__Host-")):
        raise InvalidArgumentError(
            f'The cookie name "{name}" uses a reserved prefix, which requires the "secure" flag.'
        )

    if not name.startswith("__Host-"):
        return

    if domain:
        raise InvalidArgumentError(
            f'The cookie name "{name}" uses the "__Host-" prefix, which requires no "domain".'
        )

    if path != "/":
        raise InvalidArgumentError(
            f'The cookie name "{name}" uses the "__Host-" prefix, which requires the path "/".'
        )


def _value_part(value: str, expires: datetime | None) -> str:
    """Return the cookie's value with its expiry, or the form that clears it."""
    if value == "":
        moment = datetime.now(UTC) - _DELETED_AGO
        return f"deleted; expires={format_datetime(moment, usegmt=True)}; Max-Age=0"

    part = quote(value, safe="")
    if expires is not None:
        part += _expiry_attributes(expires)

    return part


def _expiry_attributes(expires: datetime) -> str:
    """Return the expiry as both the date a person reads and the age a client counts down.

    A client honours only one of the two and which one differs, so the header
    carries both. A naive datetime is read as UTC.
    """
    moment = expires.replace(tzinfo=UTC) if expires.tzinfo is None else expires.astimezone(UTC)
    max_age = max(0, int(moment.timestamp() - datetime.now(UTC).timestamp()))

    return f"; expires={format_datetime(moment, usegmt=True)}; Max-Age={max_age}"
