"""What a session keeps of a security token: JSON, and the token rebuilt from it."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Final, TypeVar, cast, final

from typing_extensions import TypeIs, is_protocol
from xtr_password_hasher import PasswordAuthenticatedUserInterface
from xtr_security_core.authentication.token.abstract_token import AbstractToken
from xtr_security_core.exception import InvalidArgumentError
from xtr_security_core.user.password_digest import password_digest
from xtr_security_core.user.session_serializable_user_interface import (
    SessionSerializableUserInterface,
)

from ._session_kinds import kind_of, loaded_kind
from .password_session_user import PasswordSessionUser
from .session_user import SessionUser

if TYPE_CHECKING:
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["SessionTokenSerializer"]

#: The version of the envelope a token is kept in. A session value carrying
#: another is not read as a token at all.
_VERSION: Final = 1

_User = TypeVar("_User", bound=SessionSerializableUserInterface)


@final
class SessionTokenSerializer:
    """Turns a security token into the JSON envelope a session keeps, and back.

    A session holds JSON and nothing else, whatever storage keeps it, so a
    token is kept as an envelope: ``{"v": 1, "kind": …, "state": …, "user":
    …}``. The kind names the token's class as ``module:qualified name``, the
    state is what the token's own ``to_session`` answers, and the user part is
    either the user's own state — a user implementing
    :class:`~xtr_security_core.user.session_serializable_user_interface.SessionSerializableUserInterface`,
    named by its kind — or a snapshot of any other user: its identifier, its
    roles, and the digest of its password, never the hash.

    Reading is the mirror, and it never trusts the session: a kind is looked
    up only among the classes this process already loaded — the subclasses of
    the token and user contracts — and never imported, so a session can name
    nothing but a class that was meant to be rebuilt from one. Anything that is
    not such an envelope — another version, a kind no loaded class answers to,
    a state its class refuses as malformed — reads as no token; an envelope
    keeping no user rebuilds a token carrying none, for the caller to refuse.
    A snapshot is rebuilt as a :class:`SessionUser` stand-in — a
    :class:`PasswordSessionUser` when the user carried a password — for the
    firewall to reload by its identifier.
    """

    __slots__ = ()

    def encode(self, token: TokenInterface) -> dict[str, object]:
        """Return the envelope a session keeps ``token`` in.

        A switch's original is kept nested in the switch's state through this
        same method, so every refusal below holds for it too.

        Raises:
            InvalidArgumentError: When the token cannot be kept — its class
                defines no ``from_session`` of its own, one of its attributes
                does not come back from JSON exactly as it went in, or the
                state of its user does not — naming the class or the attribute
                that cannot.
        """
        token_class = type(token)
        if not isinstance(token, AbstractToken) or "from_session" not in vars(token_class):
            raise InvalidArgumentError(
                f"The token class {token_class.__qualname__} cannot be kept in a session: a "
                "token kept in one defines from_session in its own class body, so the "
                "session can rebuild it.",
            )
        for name, value in token.get_attributes().items():
            if not _round_trips(value):
                raise InvalidArgumentError(
                    f'The token attribute "{name}" cannot be kept in a session: a session '
                    "holds JSON, and the value does not come back from it as it went in — "
                    "a tuple, a set or an object. Keep a list, a string, a number, a boolean, "
                    "None or an object of them instead.",
                )
        state = token.to_session(self.encode)
        if not _round_trips(state):
            raise InvalidArgumentError(
                f"The state of the token class {token_class.__qualname__} cannot be kept in a "
                "session: a session holds JSON, and the state does not come back from it as "
                "it went in.",
            )
        return {
            "v": _VERSION,
            "kind": kind_of(token_class),
            "state": state,
            "user": _user_part(token.get_user()),
        }

    def decode(self, value: object) -> TokenInterface | None:
        """Rebuild the token a session kept as ``value``, or ``None`` when it kept none.

        ``None`` answers anything but an envelope this serializer writes, of
        a token class loaded now, whose state and user part rebuild: a
        malformed state is no token, not a failure. A user part of ``None``
        rebuilds the token with no user.
        """
        if not isinstance(value, dict):
            return None
        envelope = cast("dict[str, object]", value)
        kind = envelope.get("kind")
        state = envelope.get("state")
        if (
            envelope.get("v") != _VERSION
            or not isinstance(kind, str)
            or not isinstance(state, dict)
            or "user" not in envelope
        ):
            return None
        token_class = loaded_kind(AbstractToken, kind)
        if token_class is None or "from_session" not in vars(token_class):
            return None
        try:
            user = _user_of(envelope["user"])
            return token_class.from_session(cast("dict[str, object]", state), user, self.decode)
        except (InvalidArgumentError, TypeError, KeyError, ValueError):
            return None


def _user_part(user: UserInterface | None) -> dict[str, object] | None:
    """Return what an envelope keeps of ``user``: its own state, a snapshot, or nothing.

    Raises:
        InvalidArgumentError: When the state a user answers for itself does
            not come back from JSON exactly as it went in.
    """
    if user is None:
        return None
    if _keeps_itself(user):
        state = dict(user.to_session())
        if not _round_trips(state):
            raise InvalidArgumentError(
                f"The state of the user class {type(user).__qualname__} cannot be kept in a "
                "session: a session holds JSON, and the state its to_session answers does "
                "not come back from it as it went in.",
            )
        return {"kind": kind_of(type(user)), "state": state}
    password: str | None = None
    password_authenticated = False
    if isinstance(user, PasswordAuthenticatedUserInterface):
        password_authenticated = True
        hashed = user.get_password()
        password = None if hashed is None else password_digest(hashed)
    return {
        "kind": None,
        "identifier": user.get_user_identifier(),
        "roles": [str(role) for role in user.get_roles()],
        "password": password,
        "password_authenticated": password_authenticated,
    }


def _keeps_itself(user: UserInterface) -> TypeIs[SessionSerializableUserInterface]:
    """Tell whether ``user`` inherits the contract of a user a session keeps whole.

    By inheritance, not by shape: the class a session names is found again
    among the subclasses of the contract, so a user that merely has the two
    methods could never be rebuilt — it is kept as a snapshot instead.
    """
    return SessionSerializableUserInterface in type(user).__mro__


def _user_of(part: object) -> UserInterface | None:
    """Rebuild the user an envelope kept, or ``None`` when it kept none.

    Raises:
        InvalidArgumentError: When the part is malformed, or names a user
            class no class loaded now answers to.
    """
    if part is None:
        return None
    if not isinstance(part, dict):
        raise InvalidArgumentError("A session token's user must be an object or null.")
    fields = cast("dict[str, object]", part)
    kind = fields.get("kind")
    if kind is None:
        return _stand_in(fields)
    user_class = (
        loaded_kind(SessionSerializableUserInterface, kind) if isinstance(kind, str) else None
    )
    state = fields.get("state")
    if user_class is None or is_protocol(user_class) or not isinstance(state, dict):
        raise InvalidArgumentError(
            "A session token's user names no user class loaded now, or keeps no state.",
        )
    return _rebuilt(user_class, cast("dict[str, object]", state))


def _rebuilt(user_class: type[_User], state: dict[str, object]) -> _User:
    """Rebuild a user of ``user_class`` — a class, never the contract — from ``state``."""
    return user_class.from_session(state)


def _stand_in(fields: dict[str, object]) -> SessionUser:
    """Rebuild the snapshot an envelope kept of a user as the stand-in for it.

    Raises:
        InvalidArgumentError: When a field of the snapshot is missing or of
            the wrong type.
    """
    identifier = fields.get("identifier")
    roles = fields.get("roles")
    password = fields.get("password")
    password_authenticated = fields.get("password_authenticated")
    if (
        not isinstance(identifier, str)
        or not isinstance(roles, list)
        or not isinstance(password_authenticated, bool)
        or (password is not None and not isinstance(password, str))
    ):
        raise InvalidArgumentError("A session token's user snapshot is malformed.")
    items = cast("list[object]", roles)
    role_names = [role for role in items if isinstance(role, str)]
    if len(role_names) != len(items):
        raise InvalidArgumentError(
            "A session token's user snapshot holds a role that is no string."
        )
    if password_authenticated:
        return PasswordSessionUser(identifier, role_names, password)
    if password is not None:
        raise InvalidArgumentError(
            "A session token's user snapshot keeps a password for a user that carried none.",
        )
    return SessionUser(identifier, role_names)


def _round_trips(value: object) -> bool:
    """Tell whether ``value`` comes back from JSON exactly as it went in.

    The rule the cache-pool session storage writes by: a tuple comes back a
    list and a number keying an object a string, so neither does, and a value
    JSON cannot write at all does not either.
    """
    try:
        encoded = json.dumps(value, allow_nan=False)
    except (TypeError, ValueError):
        return False
    return cast("object", json.loads(encoded)) == value
