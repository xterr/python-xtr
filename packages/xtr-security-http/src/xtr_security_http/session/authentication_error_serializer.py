"""What a session keeps of the last authentication error: its public half, as JSON.

A failed login that redirects keeps its error for the page that renders the
form again, and the session holds JSON only: the error is kept as an envelope —
``{"v": 1, "kind": …, "message_key": …, "message_data": …}`` — of the public
half :meth:`~xtr_security_core.exception.AuthenticationError.to_session`
answers, never the internal message. Reading it back rebuilds an error of the
class the kind names, looked up among the error classes loaded now and never
imported; a kind no loaded class answers to rebuilds a plain
:class:`~xtr_security_core.exception.AuthenticationError`, since the key and
the data are all a page shows.
"""

from __future__ import annotations

from typing import Final, cast

from xtr_security_core.exception import AuthenticationError, InvalidArgumentError

from ._session_kinds import kind_of, loaded_kind

__all__ = ["authentication_error_from_session", "authentication_error_to_session"]

#: The version of the envelope an error is kept in. A session value carrying
#: another is not read as an error at all.
_VERSION: Final = 1


def authentication_error_to_session(error: AuthenticationError) -> dict[str, object]:
    """Return the envelope a session keeps ``error`` in: its kind and its public half."""
    return {"v": _VERSION, "kind": kind_of(type(error)), **error.to_session()}


def authentication_error_from_session(value: object) -> AuthenticationError | None:
    """Rebuild the error a session kept as ``value``, or ``None`` when it kept none.

    ``None`` answers anything but an envelope of this version carrying a
    string kind, a string key and an object of data — a live error a session
    held from before, a corrupt value, another version alike.
    """
    if not isinstance(value, dict):
        return None
    envelope = cast("dict[str, object]", value)
    kind = envelope.get("kind")
    message_key = envelope.get("message_key")
    message_data = envelope.get("message_data")
    if (
        envelope.get("v") != _VERSION
        or not isinstance(kind, str)
        or not isinstance(message_key, str)
        or not isinstance(message_data, dict)
    ):
        return None
    data = cast("dict[object, object]", message_data)
    keyed = {name: item for name, item in data.items() if isinstance(name, str)}
    if len(keyed) != len(data):
        return None
    error_class = loaded_kind(AuthenticationError, kind) or AuthenticationError
    try:
        return error_class.from_session(message_key, keyed)
    except (InvalidArgumentError, TypeError, KeyError, ValueError):
        return None
