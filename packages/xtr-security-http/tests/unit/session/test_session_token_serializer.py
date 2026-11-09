"""The JSON envelope a session keeps a security token in, and the token rebuilt from it."""

from __future__ import annotations

import builtins
import importlib
import json
import sys
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol, Self, cast, final

import pytest
from typing_extensions import override
from xtr_security_core.authentication.token.null_token import NullToken
from xtr_security_core.authentication.token.pre_authenticated_token import PreAuthenticatedToken
from xtr_security_core.authentication.token.remember_me_token import RememberMeToken
from xtr_security_core.authentication.token.switch_user_token import SwitchUserToken
from xtr_security_core.authentication.token.username_password_token import UsernamePasswordToken
from xtr_security_core.exception import InvalidArgumentError
from xtr_security_core.user.in_memory_user import InMemoryUser
from xtr_security_core.user.oidc_user import OidcUser
from xtr_security_core.user.password_digest import password_digest
from xtr_security_core.user.session_serializable_user_interface import (
    SessionSerializableUserInterface,
)

from xtr_security_http.authenticator.token.post_authentication_token import PostAuthenticationToken
from xtr_security_http.session import PasswordSessionUser, SessionTokenSerializer, SessionUser

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from types import ModuleType

    from xtr_security_core.authentication.token.abstract_token import AbstractToken
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.user.user_interface import UserInterface

#: A module no code in the process ever loads, for a session to name.
_NEVER_LOADED = "xtr_never_loaded_module"


@final
class _PlainUser:
    """A user that keeps no state of its own in a session, and carries no password."""

    def __init__(self, identifier: str, roles: Sequence[str] = ()) -> None:
        self._identifier = identifier
        self._roles = tuple(roles)

    def get_user_identifier(self) -> str:
        return self._identifier

    def get_roles(self) -> tuple[str, ...]:
        return self._roles


@final
class _PlainPasswordUser:
    """A user that keeps no state of its own in a session, and carries a password."""

    def __init__(self, identifier: str, password: str | None) -> None:
        self._identifier = identifier
        self._password = password

    def get_user_identifier(self) -> str:
        return self._identifier

    def get_roles(self) -> tuple[str, ...]:
        return ("ROLE_USER",)

    def get_password(self) -> str | None:
        return self._password


@final
class _TupleStateUser(SessionSerializableUserInterface):
    """A user kept whole whose state does not come back from JSON as it went in."""

    @override
    def get_user_identifier(self) -> str:
        return "ada"

    @override
    def get_roles(self) -> tuple[str, ...]:
        return ()

    @override
    def to_session(self) -> Mapping[str, object]:
        return {"roles": ("ROLE_USER",)}

    @classmethod
    @override
    def from_session(cls, state: Mapping[str, object]) -> Self:
        del state
        return cls()


class _UserContract(SessionSerializableUserInterface, Protocol):
    """A contract of the application's own, extending the one a session keeps."""


#: The kind a session would name the contract by.
_CONTRACT_KIND = f"{_UserContract.__module__}:{_UserContract.__qualname__}"


@final
class _InheritingToken(UsernamePasswordToken):
    """A token class that defines no ``from_session`` of its own."""


def _serializer() -> SessionTokenSerializer:
    return SessionTokenSerializer()


def _round_trip(token: TokenInterface) -> TokenInterface | None:
    """Keep ``token`` the way a session does — through JSON text — and rebuild it."""
    serializer = _serializer()
    kept = cast("object", json.loads(json.dumps(serializer.encode(token))))
    return serializer.decode(kept)


def _envelope(token: TokenInterface) -> dict[str, object]:
    return _serializer().encode(token)


def test_a_token_is_kept_as_an_envelope_of_its_kind_state_and_user() -> None:
    token = PostAuthenticationToken(InMemoryUser("ada", roles=["ROLE_USER"]), "main", ["ROLE_USER"])

    envelope = _envelope(token)

    assert envelope == {
        "v": 1,
        "kind": (
            "xtr_security_http.authenticator.token.post_authentication_token:"
            "PostAuthenticationToken"
        ),
        "state": {"roles": ["ROLE_USER"], "attributes": {}, "firewall": "main"},
        "user": {
            "kind": "xtr_security_core.user.in_memory_user:InMemoryUser",
            "state": {
                "identifier": "ada",
                "password": None,
                "roles": ["ROLE_USER"],
                "enabled": True,
            },
        },
    }


def test_the_envelope_comes_back_from_json_as_it_went_in() -> None:
    token = PostAuthenticationToken(InMemoryUser("ada"), "main", ["ROLE_USER"])
    token.set_authentication_proofs({"pwd": 1_700_000_000})
    token.set_attribute("oidc_id_token", "header.payload.signature")

    envelope = _envelope(token)

    assert json.loads(json.dumps(envelope, allow_nan=False)) == envelope


@pytest.mark.parametrize(
    "token",
    [
        UsernamePasswordToken(InMemoryUser("ada"), "main", ["ROLE_USER"]),
        RememberMeToken(InMemoryUser("ada", roles=["ROLE_USER"]), "main"),
        PreAuthenticatedToken(InMemoryUser("ada"), "main", ["ROLE_USER"]),
        PostAuthenticationToken(InMemoryUser("ada"), "main", ["ROLE_USER"]),
    ],
    ids=["username-password", "remember-me", "pre-authenticated", "post-authentication"],
)
def test_every_token_kind_is_rebuilt_as_its_own_class(token: AbstractToken) -> None:
    rebuilt = _round_trip(token)

    assert type(rebuilt) is type(token)
    assert rebuilt is not None
    assert rebuilt.get_user_identifier() == "ada"
    assert rebuilt.get_role_names() == ("ROLE_USER",)


def test_a_switch_is_rebuilt_with_its_original_and_where_it_was_made() -> None:
    original = UsernamePasswordToken(InMemoryUser("admin"), "main", ["ROLE_ADMIN"])
    switch = SwitchUserToken(InMemoryUser("ada"), "main", ["ROLE_USER"], original, "/admin")

    rebuilt = _round_trip(switch)

    assert isinstance(rebuilt, SwitchUserToken)
    assert rebuilt.get_user_identifier() == "ada"
    assert rebuilt.get_originated_from_uri() == "/admin"
    rebuilt_original = rebuilt.get_original_token()
    assert type(rebuilt_original) is UsernamePasswordToken
    assert rebuilt_original.get_user_identifier() == "admin"
    assert rebuilt_original.get_role_names() == ("ROLE_ADMIN",)


def test_an_in_memory_user_is_rebuilt_as_itself_with_its_password_as_its_digest() -> None:
    token = PostAuthenticationToken(InMemoryUser("ada", password="hashed"), "main", [])  # noqa: S106 -- a test fixture password, not a secret

    rebuilt = _round_trip(token)

    assert rebuilt is not None
    assert rebuilt.get_user() == InMemoryUser("ada", password=password_digest("hashed"))


def test_an_oidc_user_is_rebuilt_as_itself_with_every_claim() -> None:
    user = OidcUser(
        sub="ada",
        email="ada@example.test",
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        tenant="acme",
    )
    token = PostAuthenticationToken(user, "main", ["ROLE_USER"])

    rebuilt = _round_trip(token)

    assert rebuilt is not None
    rebuilt_user = rebuilt.get_user()
    assert isinstance(rebuilt_user, OidcUser)
    assert rebuilt_user.get_email() == "ada@example.test"
    assert rebuilt_user.get_updated_at() == datetime(2026, 1, 1, tzinfo=UTC)
    assert dict(rebuilt_user.get_additional_claims()) == {"tenant": "acme"}


def test_any_other_user_is_kept_as_a_snapshot_of_its_identifier_roles_and_digest() -> None:
    envelope = _envelope(
        PostAuthenticationToken(_PlainPasswordUser("ada", "$argon2id$hash"), "main", [])
    )

    assert envelope["user"] == {
        "kind": None,
        "identifier": "ada",
        "roles": ["ROLE_USER"],
        "password": password_digest("$argon2id$hash"),
        "password_authenticated": True,
    }


@pytest.mark.parametrize(
    "user",
    [
        InMemoryUser("ada", password="$argon2id$v=19$the-hash"),  # noqa: S106 -- a test fixture password, not a secret
        _PlainPasswordUser("ada", "$argon2id$v=19$the-hash"),
    ],
    ids=["kept-whole", "snapshot"],
)
def test_the_session_never_keeps_the_password_hash(user: UserInterface) -> None:
    envelope = _envelope(PostAuthenticationToken(user, "main", []))

    assert "$argon2id$v=19$the-hash" not in json.dumps(envelope)


def test_a_password_carrying_snapshot_is_rebuilt_as_a_password_stand_in() -> None:
    rebuilt = _round_trip(PostAuthenticationToken(_PlainPasswordUser("ada", "hashed"), "main", []))

    assert rebuilt is not None
    stand_in = rebuilt.get_user()
    assert isinstance(stand_in, PasswordSessionUser)
    assert stand_in.get_user_identifier() == "ada"
    assert stand_in.get_roles() == ("ROLE_USER",)
    assert stand_in.get_password() == password_digest("hashed")


def test_a_snapshot_of_a_password_carrying_user_without_a_password_keeps_none() -> None:
    rebuilt = _round_trip(PostAuthenticationToken(_PlainPasswordUser("ada", None), "main", []))

    assert rebuilt is not None
    stand_in = rebuilt.get_user()
    assert isinstance(stand_in, PasswordSessionUser)
    assert stand_in.get_password() is None


def test_a_snapshot_of_a_user_without_a_password_is_rebuilt_as_a_plain_stand_in() -> None:
    rebuilt = _round_trip(
        PostAuthenticationToken(_PlainUser("ada", ["ROLE_USER"]), "main", ["ROLE_USER"])
    )

    assert rebuilt is not None
    stand_in = rebuilt.get_user()
    assert type(stand_in) is SessionUser
    assert stand_in.get_user_identifier() == "ada"
    assert stand_in.get_roles() == ("ROLE_USER",)


def test_a_token_kept_with_no_user_is_rebuilt_with_none() -> None:
    envelope = {**_envelope(UsernamePasswordToken(InMemoryUser("ada"), "main")), "user": None}

    rebuilt = _serializer().decode(envelope)

    assert isinstance(rebuilt, UsernamePasswordToken)
    assert rebuilt.get_user() is None


def test_a_token_class_without_its_own_from_session_is_refused_naming_it() -> None:
    with pytest.raises(InvalidArgumentError, match="_InheritingToken cannot be kept"):
        _ = _envelope(_InheritingToken(InMemoryUser("ada"), "main"))


def test_a_token_that_is_no_abstract_token_is_refused_naming_its_class() -> None:
    with pytest.raises(InvalidArgumentError, match="NullToken cannot be kept"):
        _ = _envelope(NullToken())


def test_a_switch_whose_original_cannot_be_kept_is_refused_naming_the_original() -> None:
    switch = SwitchUserToken(InMemoryUser("ada"), "main", [], NullToken())

    with pytest.raises(InvalidArgumentError, match="NullToken cannot be kept"):
        _ = _envelope(switch)


@pytest.mark.parametrize(
    "value",
    [("read", "write"), {"read", "write"}, object(), {1: "read"}, float("nan")],
    ids=["tuple", "set", "object", "number-keyed", "nan"],
)
def test_an_attribute_that_does_not_come_back_from_json_is_refused_naming_it(
    value: object,
) -> None:
    token = PostAuthenticationToken(InMemoryUser("ada"), "main", [])
    token.set_attribute("scopes", value)

    with pytest.raises(InvalidArgumentError, match='"scopes"'):
        _ = _envelope(token)


def test_a_user_state_that_does_not_come_back_from_json_is_refused_naming_the_class() -> None:
    with pytest.raises(InvalidArgumentError, match="_TupleStateUser"):
        _ = _envelope(PostAuthenticationToken(_TupleStateUser(), "main", []))


@pytest.mark.parametrize(
    "value",
    [
        None,
        "a token",
        ["v", 1],
        1,
        PostAuthenticationToken(InMemoryUser("ada"), "main", []),
    ],
    ids=["none", "string", "list", "number", "live-token"],
)
def test_a_value_that_is_no_envelope_is_no_token(value: object) -> None:
    assert _serializer().decode(value) is None


def _altered(token: TokenInterface, **fields: object) -> dict[str, object]:
    """Return the envelope of ``token`` with ``fields`` replaced."""
    return {**_envelope(token), **fields}


def _ada() -> PostAuthenticationToken:
    return PostAuthenticationToken(InMemoryUser("ada"), "main", ["ROLE_USER"])


@pytest.mark.parametrize(
    "envelope",
    [
        _altered(_ada(), v=2),
        _altered(_ada(), v="1"),
        _altered(_ada(), kind="xtr_security_http.nowhere:PostAuthenticationToken"),
        _altered(_ada(), kind=None),
        _altered(_ada(), kind=f"{__name__}:_InheritingToken"),
        _altered(_ada(), state=["roles"]),
        _altered(_ada(), state={"roles": ["ROLE_USER"], "attributes": {}}),
        _altered(_ada(), state={"roles": "ROLE_USER", "attributes": {}, "firewall": "main"}),
        _altered(_ada(), user="ada"),
        _altered(_ada(), user={"kind": "xtr_security_core.user.nowhere:InMemoryUser", "state": {}}),
        _altered(_ada(), user={"kind": _CONTRACT_KIND, "state": {}}),
        _altered(_ada(), user={"kind": "xtr_security_core.user.in_memory_user:InMemoryUser"}),
        _altered(
            _ada(),
            user={
                "kind": "xtr_security_core.user.in_memory_user:InMemoryUser",
                "state": {"identifier": "ada", "password": None, "roles": [], "enabled": "yes"},
            },
        ),
        _altered(_ada(), user={"kind": None, "identifier": "ada", "roles": "ROLE_USER"}),
        _altered(
            _ada(),
            user={
                "kind": None,
                "identifier": "ada",
                "roles": [],
                "password": "e3069283",
                "password_authenticated": False,
            },
        ),
    ],
    ids=[
        "another-version",
        "a-version-spelled-as-text",
        "unknown-token-kind",
        "no-token-kind",
        "token-kind-without-its-own-from-session",
        "state-no-object",
        "state-without-a-firewall",
        "state-roles-no-list",
        "user-no-object",
        "unknown-user-kind",
        "user-kind-of-a-contract",
        "user-without-a-state",
        "user-state-malformed",
        "snapshot-roles-no-list",
        "snapshot-password-of-a-user-carrying-none",
    ],
)
def test_an_envelope_that_does_not_rebuild_is_no_token(envelope: dict[str, object]) -> None:
    assert _serializer().decode(envelope) is None


def test_an_envelope_without_a_user_part_is_no_token() -> None:
    envelope = _envelope(_ada())
    del envelope["user"]

    assert _serializer().decode(envelope) is None


def _refusing(
    real: Callable[..., ModuleType],
    imported: list[str],
) -> Callable[..., ModuleType]:
    """Return ``real``, recording every attempt to import the never-loaded module."""

    def guarded(name: str, *arguments: object, **keywords: object) -> ModuleType:
        if name.partition(".")[0] == _NEVER_LOADED:
            imported.append(name)
            raise AssertionError(f"A session value made the process import {name}.")
        return real(name, *arguments, **keywords)

    return guarded


def test_a_kind_naming_a_module_not_loaded_is_never_imported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    imported: list[str] = []
    monkeypatch.setattr(builtins, "__import__", _refusing(builtins.__import__, imported))
    monkeypatch.setattr(importlib, "import_module", _refusing(importlib.import_module, imported))
    serializer = _serializer()

    token = serializer.decode(_altered(_ada(), kind=f"{_NEVER_LOADED}:Token"))
    user = serializer.decode(_altered(_ada(), user={"kind": f"{_NEVER_LOADED}:User", "state": {}}))

    assert (token, user) == (None, None)
    assert imported == []
    assert _NEVER_LOADED not in sys.modules
