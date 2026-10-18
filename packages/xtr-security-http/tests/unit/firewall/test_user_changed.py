"""The comparison that decides a refreshed user is another user."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_security_core.user.in_memory_user import InMemoryUser

from xtr_security_http.authenticator.token.post_authentication_token import PostAuthenticationToken

if TYPE_CHECKING:
    from xtr_security_core.user.user_interface import UserInterface

from xtr_security_http.firewall.user_changed import _crc32c, has_user_changed


@final
class _PlainPasswordUser:
    """A password-carrying user that does not compare itself.

    The in-memory user implements the equatable contract, so it answers the
    comparison itself and the field-by-field rules below it never run; this
    user leaves them to do the comparing.
    """

    def __init__(
        self, identifier: str, password: str | None = None, roles: tuple[str, ...] = ()
    ) -> None:
        self._identifier = identifier
        self._password = password
        self._roles = roles

    def get_user_identifier(self) -> str:
        return self._identifier

    def get_roles(self) -> tuple[str, ...]:
        return self._roles

    def get_password(self) -> str | None:
        return self._password


@final
class _AlwaysEqualUser:
    """A user that says every comparison is the same user."""

    def get_user_identifier(self) -> str:
        return "ada"

    def get_roles(self) -> tuple[str, ...]:
        return ()

    def is_equal_to(self, user: UserInterface) -> bool:
        del user
        return True


def _token(user: UserInterface, roles: tuple[str, ...] = ()) -> PostAuthenticationToken:
    return PostAuthenticationToken(user, "main", roles)


def test_the_checksum_matches_the_catalogue_vector() -> None:
    assert _crc32c("123456789") == "e3069283"


def test_an_unchanged_user_has_not_changed() -> None:
    user = _PlainPasswordUser("ada", "hashed", ("ROLE_USER",))
    token = _token(user, ("ROLE_USER",))

    changed = has_user_changed(token, user, _PlainPasswordUser("ada", "hashed", ("ROLE_USER",)))

    assert changed is False


def test_a_changed_password_has_changed() -> None:
    user = _PlainPasswordUser("ada", "hashed")
    token = _token(user)

    assert has_user_changed(token, user, _PlainPasswordUser("ada", "rehashed")) is True


def test_a_password_abbreviated_as_its_checksum_has_not_changed() -> None:
    """The legacy carve-out: eight characters that spell the crc32c of the reloaded password."""
    user = _PlainPasswordUser("ada", _crc32c("new-password"))
    token = _token(user)

    changed = has_user_changed(token, user, _PlainPasswordUser("ada", "new-password"))

    assert changed is False


def test_a_checksum_shaped_password_of_another_password_has_changed() -> None:
    """Eight characters that are not the checksum of the reloaded password."""
    user = _PlainPasswordUser("ada", "e3069283")
    token = _token(user)

    assert has_user_changed(token, user, _PlainPasswordUser("ada", "other")) is True


def test_a_user_that_stopped_carrying_a_password_has_changed() -> None:
    user = _PlainPasswordUser("ada", "hashed")
    token = _token(user)

    assert has_user_changed(token, user, _PlainPasswordUser("ada")) is True


def test_a_role_granted_or_withdrawn_has_changed() -> None:
    """The token's role names are weighed, not the original user's."""
    user = _PlainPasswordUser("ada", roles=("ROLE_USER",))
    token = _token(user, ("ROLE_USER",))

    granted = has_user_changed(
        token, user, _PlainPasswordUser("ada", roles=("ROLE_USER", "ROLE_ADMIN"))
    )
    withdrawn = has_user_changed(token, user, _PlainPasswordUser("ada", roles=()))

    assert granted is True
    assert withdrawn is True


def test_another_identifier_has_changed() -> None:
    user = _PlainPasswordUser("ada")
    token = _token(user)

    assert has_user_changed(token, user, _PlainPasswordUser("lin")) is True


def test_a_user_that_compares_itself_answers_for_everyone() -> None:
    """The equatable contract short-circuits the field-by-field comparison."""
    user = _AlwaysEqualUser()
    token = _token(user)

    changed = has_user_changed(token, user, _PlainPasswordUser("lin", "other"))

    assert changed is False


def test_an_equatable_user_that_differs_has_changed() -> None:
    """The in-memory user compares itself field for field, and a difference counts."""
    user = InMemoryUser("ada", password="hashed")  # noqa: S106 -- a test fixture password, not a secret
    token = _token(user)

    assert (
        has_user_changed(token, user, InMemoryUser("ada", password="rehashed"))  # noqa: S106 -- a test fixture password, not a secret
        is True
    )
