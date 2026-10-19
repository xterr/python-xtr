"""The chain step that carries an authenticated user across requests."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from starlette.datastructures import MutableHeaders
from xtr_event_dispatcher import EventDispatcher
from xtr_http_foundation import MemorySessionStorage, Session
from xtr_http_kernel import RequestEvent, ResponseEvent
from xtr_security_core.authentication.token.null_token import NullToken
from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.authentication.token.switch_user_token import SwitchUserToken
from xtr_security_core.exception import (
    AuthenticationError,
    InvalidArgumentError,
    UnsupportedUserError,
    UserNotFoundError,
)
from xtr_security_core.user.in_memory_user import InMemoryUser

from tests.support.dispatchers import RecordingDispatcher
from tests.support.messages import make_message
from xtr_security_http._security_state import SecurityState, security_state_of
from xtr_security_http.authenticator.token.post_authentication_token import PostAuthenticationToken
from xtr_security_http.event.check_refreshed_user_event import CheckRefreshedUserEvent
from xtr_security_http.event.token_deauthenticated_event import TokenDeauthenticatedEvent
from xtr_security_http.firewall.context_listener import ContextListener
from xtr_security_http.firewall.user_changed import _crc32c
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_http_foundation import SessionStorageInterface
    from xtr_security_core.user.user_interface import UserInterface
    from xtr_security_core.user.user_provider_interface import UserProviderInterface

pytestmark = pytest.mark.anyio

#: The session key a firewall named ``main`` stores its context under.
_MAIN_KEY = "_security.main"


@final
class _PlainPasswordUser:
    """A password-carrying user that does not compare itself.

    The in-memory user implements the equatable contract, so it answers the
    refresh comparison itself and the field-by-field rules never run; this
    user leaves them to do the comparing.
    """

    def __init__(self, identifier: str, password: str | None = None) -> None:
        self._identifier = identifier
        self._password = password

    def get_user_identifier(self) -> str:
        return self._identifier

    def get_roles(self) -> tuple[str, ...]:
        return ()

    def get_password(self) -> str | None:
        return self._password


@final
class _FakeProvider:
    """A user provider answering what it was built with."""

    def __init__(
        self,
        *,
        supports: bool = True,
        refreshed: UserInterface | None = None,
        error: Exception | None = None,
    ) -> None:
        self._supports = supports
        self._refreshed = refreshed
        self._error = error

    async def load_user_by_identifier(self, identifier: str) -> UserInterface:
        return InMemoryUser(identifier)

    async def refresh_user(self, user: UserInterface) -> UserInterface:
        del user  # the provider answers from what it was built with, not from the user
        if self._error is not None:
            raise self._error
        assert self._refreshed is not None
        return self._refreshed

    def supports_class(self, user_class: type) -> bool:
        del user_class
        return self._supports


def _listener(
    providers: tuple[UserProviderInterface, ...] = (),
    *,
    storage: TokenStorage | None = None,
    session_storage: SessionStorageInterface | None = None,
    context_key: str = "main",
) -> ContextListener:
    return ContextListener(
        storage if storage is not None else TokenStorage(),
        providers,
        context_key,
        session_storage if session_storage is not None else MemorySessionStorage(),
    )


def _request_event(cookie_session_id: str | None = None) -> RequestEvent:
    """Return a request event, reattaching ``cookie_session_id`` when given."""
    request = make_message(path="/account")
    if cookie_session_id is not None:
        request = request.with_cookie_params({"xtr_session": cookie_session_id})
    return RequestEvent(request, {})


def _response_event(state: dict[str, object]) -> ResponseEvent:
    """Return a response event over the same state bag the request half used."""
    return ResponseEvent(
        make_message(path="/account"),
        state,
        200,
        MutableHeaders(),
    )


async def _session_holding(
    session_storage: SessionStorageInterface,
    key: str,
    value: object,
) -> str:
    """Store ``value`` under ``key`` in a saved session, and return the session's ID."""
    session = Session(session_storage)
    await session.set(key, value)
    await session.save()
    return session.get_id()


def _token(user: UserInterface, roles: tuple[str, ...] = ()) -> PostAuthenticationToken:
    return PostAuthenticationToken(user, "main", roles)


async def test_supports_answers_the_lazy_join_on_every_request() -> None:
    listener = _listener()

    assert await listener.supports(make_message()) is None


def test_the_chain_position_is_the_default_priority() -> None:
    """Tied with the authentication step, ahead of the access step at -255."""
    assert ContextListener.get_priority() == 0


def test_an_empty_context_key_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = _listener(context_key="")


async def test_a_session_token_is_restored_refreshed_and_stored() -> None:
    """The provider's fresh copy of the user is what the storage ends up holding."""
    session_storage = MemorySessionStorage()
    user = InMemoryUser("ada", password="hashed", roles=("ROLE_USER",))  # noqa: S106 -- a test fixture password, not a secret
    session_id = await _session_holding(session_storage, _MAIN_KEY, _token(user, ("ROLE_USER",)))
    storage = TokenStorage()
    provider = _FakeProvider(
        refreshed=InMemoryUser("ada", password="hashed", roles=("ROLE_USER",)),  # noqa: S106 -- a test fixture password, not a secret
    )
    listener = _listener((provider,), storage=storage, session_storage=session_storage)

    await listener.authenticate(_request_event(session_id))

    stored = storage.get_token()
    assert stored is not None
    assert stored.get_user() is not user  # the provider's fresh copy, not the stored one
    assert stored.get_user_identifier() == "ada"


async def test_the_request_marks_the_firewall_run_and_parks_the_session() -> None:
    session_storage = MemorySessionStorage()
    session_id = await _session_holding(session_storage, _MAIN_KEY, _token(InMemoryUser("ada")))
    listener = _listener(
        (_FakeProvider(refreshed=InMemoryUser("ada")),),
        session_storage=session_storage,
    )
    event = _request_event(session_id)

    await listener.authenticate(event)

    state: SecurityState = security_state_of(event.state)
    assert state.attributes[SecurityRequestAttributes.FIREWALL_RUN] == _MAIN_KEY
    parked = state.attributes[SecurityRequestAttributes.SESSION]
    assert isinstance(parked, Session)


async def test_a_session_without_a_token_leaves_the_storage_empty() -> None:
    session_storage = MemorySessionStorage()
    session_id = await _session_holding(session_storage, "unrelated", "value")
    storage = TokenStorage()
    listener = _listener(
        (_FakeProvider(refreshed=InMemoryUser("ada")),),
        storage=storage,
        session_storage=session_storage,
    )

    await listener.authenticate(_request_event(session_id))

    assert storage.get_token() is None


async def test_a_corrupt_payload_leaves_the_storage_empty_without_failing_the_request() -> None:
    session_storage = MemorySessionStorage()
    session_id = await _session_holding(session_storage, _MAIN_KEY, "not a token at all")
    storage = TokenStorage()
    listener = _listener(
        (_FakeProvider(refreshed=InMemoryUser("ada")),),
        storage=storage,
        session_storage=session_storage,
    )

    await listener.authenticate(_request_event(session_id))

    assert storage.get_token() is None


async def test_a_foreign_object_payload_leaves_the_storage_empty() -> None:
    session_storage = MemorySessionStorage()
    session_id = await _session_holding(session_storage, _MAIN_KEY, {"identifier": "ada"})
    storage = TokenStorage()
    listener = _listener(
        (_FakeProvider(refreshed=InMemoryUser("ada")),),
        storage=storage,
        session_storage=session_storage,
    )

    await listener.authenticate(_request_event(session_id))

    assert storage.get_token() is None


async def test_a_token_without_a_user_is_refused() -> None:
    session_storage = MemorySessionStorage()
    session_id = await _session_holding(session_storage, _MAIN_KEY, NullToken())

    with pytest.raises(InvalidArgumentError):
        await _listener(session_storage=session_storage).authenticate(_request_event(session_id))


async def test_a_provider_not_supporting_the_class_is_skipped() -> None:
    """The refresh runs through the providers in order, past the ones that pass."""
    session_storage = MemorySessionStorage()
    user = InMemoryUser("ada")
    session_id = await _session_holding(session_storage, _MAIN_KEY, _token(user))
    storage = TokenStorage()
    refusing = _FakeProvider(supports=False, refreshed=InMemoryUser("refused"))
    answering = _FakeProvider(refreshed=InMemoryUser("ada"))
    listener = _listener((refusing, answering), storage=storage, session_storage=session_storage)

    await listener.authenticate(_request_event(session_id))

    stored = storage.get_token()
    assert stored is not None
    assert stored.get_user_identifier() == "ada"


async def test_a_provider_refusing_the_user_hands_it_to_the_next() -> None:
    session_storage = MemorySessionStorage()
    session_id = await _session_holding(
        session_storage,
        _MAIN_KEY,
        _token(InMemoryUser("ada")),
    )
    storage = TokenStorage()
    refusing = _FakeProvider(error=UnsupportedUserError("Not mine."))
    answering = _FakeProvider(refreshed=InMemoryUser("ada"))
    listener = _listener((refusing, answering), storage=storage, session_storage=session_storage)

    await listener.authenticate(_request_event(session_id))

    assert storage.get_token() is not None


async def test_a_changed_user_deauthenticates_and_announces_the_event() -> None:
    session_storage = MemorySessionStorage()
    user = InMemoryUser("ada", password="hashed")  # noqa: S106 -- a test fixture password, not a secret
    original = _token(user)
    session_id = await _session_holding(session_storage, _MAIN_KEY, original)
    storage = TokenStorage()
    provider = _FakeProvider(refreshed=InMemoryUser("ada", password="rehashed"))  # noqa: S106 -- a test fixture password, not a secret
    dispatcher = EventDispatcher()
    announced: list[TokenDeauthenticatedEvent] = []
    dispatcher.add_listener(
        TokenDeauthenticatedEvent,
        _record_deauthentication(announced),
    )
    listener = ContextListener(
        storage,
        (provider,),
        "main",
        session_storage,
        dispatcher=dispatcher,
    )

    await listener.authenticate(_request_event(session_id))

    assert storage.get_token() is None
    assert len(announced) == 1
    event = announced[0]
    assert event.get_original_token() is original
    assert event.get_reason() == "the user has changed"
    assert event.get_provider_classes() == (_FakeProvider,)
    assert event.get_exception() is None


def _record_deauthentication(
    announced: list[TokenDeauthenticatedEvent],
) -> Callable[[TokenDeauthenticatedEvent], object]:
    """Return a listener appending every deauthentication event to ``announced``."""

    async def record(event: TokenDeauthenticatedEvent) -> None:
        announced.append(event)

    return record


async def test_a_user_no_provider_finds_deauthenticates_with_its_own_reason() -> None:
    session_storage = MemorySessionStorage()
    session_id = await _session_holding(
        session_storage,
        _MAIN_KEY,
        _token(InMemoryUser("ada")),
    )
    storage = TokenStorage()
    provider = _FakeProvider(error=UserNotFoundError("ada"))
    dispatcher = EventDispatcher()
    announced: list[TokenDeauthenticatedEvent] = []
    dispatcher.add_listener(TokenDeauthenticatedEvent, _record_deauthentication(announced))
    listener = ContextListener(
        storage,
        (provider,),
        "main",
        session_storage,
        dispatcher=dispatcher,
    )

    await listener.authenticate(_request_event(session_id))

    assert storage.get_token() is None
    assert len(announced) == 1
    assert announced[0].get_reason() == "the user could not be found by any user provider"
    assert announced[0].get_provider_classes() == (_FakeProvider,)


async def test_no_provider_for_the_class_is_refused() -> None:
    session_storage = MemorySessionStorage()
    session_id = await _session_holding(
        session_storage,
        _MAIN_KEY,
        _token(InMemoryUser("ada")),
    )
    listener = _listener((_FakeProvider(supports=False),), session_storage=session_storage)

    with pytest.raises(UnsupportedUserError):
        await listener.authenticate(_request_event(session_id))


async def test_a_listener_may_deauthenticate_with_its_own_reason() -> None:
    """The refreshed-user check lets a listener add a reason the built-in comparison missed."""
    session_storage = MemorySessionStorage()
    user = InMemoryUser("ada", password="hashed")  # noqa: S106 -- a test fixture password, not a secret
    session_id = await _session_holding(session_storage, _MAIN_KEY, _token(user))
    storage = TokenStorage()
    provider = _FakeProvider(refreshed=InMemoryUser("ada", password="hashed"))  # noqa: S106 -- a test fixture password, not a secret
    dispatcher = EventDispatcher()
    reason = AuthenticationError("The account was disabled.")

    async def disable(event: CheckRefreshedUserEvent) -> None:
        event.set_user_changed(True, reason)  # noqa: FBT003 -- the event's own signature takes the verdict positionally

    dispatcher.add_listener(CheckRefreshedUserEvent, disable)
    announced: list[TokenDeauthenticatedEvent] = []
    dispatcher.add_listener(TokenDeauthenticatedEvent, _record_deauthentication(announced))
    listener = ContextListener(
        storage,
        (provider,),
        "main",
        session_storage,
        dispatcher=dispatcher,
    )

    await listener.authenticate(_request_event(session_id))

    assert storage.get_token() is None
    assert len(announced) == 1
    assert announced[0].get_reason() == str(reason)
    assert announced[0].get_exception() is reason


async def test_a_listener_may_clear_the_builtin_verdict() -> None:
    session_storage = MemorySessionStorage()
    user = InMemoryUser("ada", password="hashed")  # noqa: S106 -- a test fixture password, not a secret
    session_id = await _session_holding(session_storage, _MAIN_KEY, _token(user))
    storage = TokenStorage()
    provider = _FakeProvider(refreshed=InMemoryUser("ada", password="rehashed"))  # noqa: S106 -- a test fixture password, not a secret
    dispatcher = EventDispatcher()

    async def keep(event: CheckRefreshedUserEvent) -> None:
        event.set_user_changed(False)

    dispatcher.add_listener(CheckRefreshedUserEvent, keep)
    listener = ContextListener(
        storage,
        (provider,),
        "main",
        session_storage,
        dispatcher=dispatcher,
    )

    await listener.authenticate(_request_event(session_id))

    assert storage.get_token() is not None


async def test_a_password_abbreviated_as_its_checksum_does_not_log_out() -> None:
    """The legacy carve-out, through the listener: the checksum is the same password."""
    session_storage = MemorySessionStorage()
    user = _PlainPasswordUser("ada", _crc32c("new-password"))
    session_id = await _session_holding(session_storage, _MAIN_KEY, _token(user))
    storage = TokenStorage()
    provider = _FakeProvider(refreshed=_PlainPasswordUser("ada", "new-password"))
    listener = _listener((provider,), storage=storage, session_storage=session_storage)

    await listener.authenticate(_request_event(session_id))

    assert storage.get_token() is not None


async def test_the_response_half_stores_the_authenticated_token() -> None:
    session_storage = MemorySessionStorage()
    session_id = await _session_holding(session_storage, "unrelated", None)
    storage = TokenStorage()
    listener = _listener(session_storage=session_storage, storage=storage)
    state: dict[str, object] = {}
    request_event = _request_event(session_id)
    await listener.authenticate(request_event)
    # The request half parks the session and the mark on the same bag the
    # response event carries.
    state.update(request_event.state)
    token = _token(InMemoryUser("ada"), ("ROLE_USER",))
    storage.set_token(token)

    await listener.on_response(_response_event(state))

    parked = security_state_of(state).attributes[SecurityRequestAttributes.SESSION]
    assert isinstance(parked, Session)
    assert await parked.get(_MAIN_KEY) is token


async def test_the_response_half_removes_the_key_of_an_anonymous_request() -> None:
    session_storage = MemorySessionStorage()
    session_id = await _session_holding(session_storage, _MAIN_KEY, _token(InMemoryUser("ada")))
    storage = TokenStorage()
    provider = _FakeProvider(refreshed=InMemoryUser("ada"))
    listener = _listener((provider,), session_storage=session_storage, storage=storage)
    request_event = _request_event(session_id)
    await listener.authenticate(request_event)
    state: dict[str, object] = {}
    state.update(request_event.state)
    # The request stored the token; a logout empties the storage before the
    # response, which is what the removal answers.
    assert storage.get_token() is not None
    storage.set_token(None)

    await listener.on_response(_response_event(state))

    parked = security_state_of(state).attributes[SecurityRequestAttributes.SESSION]
    assert isinstance(parked, Session)
    assert await parked.get(_MAIN_KEY) is None


async def test_the_response_half_skips_a_request_the_listener_never_ran() -> None:
    """No firewall-run mark: the response is not this listener's to store."""
    session_storage = MemorySessionStorage()
    session_id = await _session_holding(session_storage, _MAIN_KEY, "sentinel")
    storage = TokenStorage()
    storage.set_token(_token(InMemoryUser("ada")))
    listener = _listener(session_storage=session_storage, storage=storage)
    state: dict[str, object] = {}
    # A request another firewall ran: a session and a token, but no mark of
    # this listener's own key.
    session = Session(session_storage, cookie_value=session_id)
    await session.start()
    security_state_of(state).attributes[SecurityRequestAttributes.SESSION] = session

    await listener.on_response(_response_event(state))

    assert await session.get(_MAIN_KEY) == "sentinel"


async def test_the_response_half_skips_a_mark_of_another_firewall() -> None:
    session_storage = MemorySessionStorage()
    session_id = await _session_holding(session_storage, _MAIN_KEY, "sentinel")
    storage = TokenStorage()
    storage.set_token(_token(InMemoryUser("ada")))
    listener = _listener(session_storage=session_storage, storage=storage)
    state: dict[str, object] = {}
    session = Session(session_storage, cookie_value=session_id)
    await session.start()
    marked = security_state_of(state).attributes
    marked[SecurityRequestAttributes.FIREWALL_RUN] = "_security.other"
    marked[SecurityRequestAttributes.SESSION] = session

    await listener.on_response(_response_event(state))

    assert await session.get(_MAIN_KEY) == "sentinel"


async def test_the_response_half_skips_a_request_without_a_session() -> None:
    """No session parked: nothing to store into, and no failure."""
    storage = TokenStorage()
    storage.set_token(_token(InMemoryUser("ada")))
    listener = _listener(storage=storage)
    state: dict[str, object] = {}
    security_state_of(state).attributes[SecurityRequestAttributes.FIREWALL_RUN] = _MAIN_KEY

    await listener.on_response(_response_event(state))


@final
class _PerUserProvider:
    """Reloads each user as a fresh copy of the one it was asked for."""

    __slots__ = ("refreshed_users",)

    def __init__(self) -> None:
        self.refreshed_users: dict[str, InMemoryUser] = {}

    async def refresh_user(self, user: UserInterface) -> InMemoryUser:
        """Answer a fresh user of the same identifier, recording the reload."""
        refreshed = InMemoryUser(user.get_user_identifier())
        self.refreshed_users[user.get_user_identifier()] = refreshed
        return refreshed

    async def load_user_by_identifier(self, identifier: str) -> InMemoryUser:
        """Load the user named by ``identifier``."""
        return InMemoryUser(identifier)

    def supports_class(self, user_class: type) -> bool:
        """Tell whether ``user_class`` is the in-memory user."""
        return issubclass(user_class, InMemoryUser)


@final
class _ChangedPasswordProvider:
    """Reloads one user changed, and every other as a fresh copy of itself."""

    __slots__ = ("_changed_identifier",)

    def __init__(self, changed_identifier: str) -> None:
        self._changed_identifier = changed_identifier

    async def refresh_user(self, user: UserInterface) -> InMemoryUser:
        """Answer the changed user for the one identifier, a fresh copy for the rest."""
        if user.get_user_identifier() == self._changed_identifier:
            return InMemoryUser(
                user.get_user_identifier(),
                password="rehashed",  # noqa: S106 -- a test password, not a credential
            )
        return InMemoryUser(user.get_user_identifier())

    async def load_user_by_identifier(self, identifier: str) -> InMemoryUser:
        """Load the user named by ``identifier``."""
        return InMemoryUser(identifier)

    def supports_class(self, user_class: type) -> bool:
        """Tell whether ``user_class`` is the in-memory user."""
        return issubclass(user_class, InMemoryUser)


async def test_a_switch_token_refreshes_the_original_user_first() -> None:
    """The impersonator's token is reloaded before the switched one, both holding fresh users."""
    provider = _PerUserProvider()
    original = _token(InMemoryUser("admin"))
    switched = SwitchUserToken(InMemoryUser("ada"), "main", ("ROLE_USER",), original)
    session_storage = MemorySessionStorage()
    session_id = await _session_holding(session_storage, _MAIN_KEY, switched)
    storage = TokenStorage()
    listener = _listener((provider,), session_storage=session_storage, storage=storage)

    await listener.authenticate(_request_event(session_id))

    stored = storage.get_token()
    assert stored is switched
    assert isinstance(stored, SwitchUserToken)
    assert stored.get_original_token().get_user() is provider.refreshed_users["admin"]
    assert stored.get_user() is provider.refreshed_users["ada"]


async def test_a_deauthenticated_original_deauthenticates_the_switch_with_its_result() -> None:
    """A reload that ends the impersonator's session ends the switch with the same reason."""
    provider = _ChangedPasswordProvider("admin")
    original = _token(InMemoryUser("admin"))
    switched = SwitchUserToken(InMemoryUser("ada"), "main", ("ROLE_USER",), original)
    session_storage = MemorySessionStorage()
    session_id = await _session_holding(session_storage, _MAIN_KEY, switched)
    storage = TokenStorage()
    dispatcher = RecordingDispatcher()
    listener = ContextListener(
        storage,
        (provider,),
        "main",
        session_storage,
        dispatcher=dispatcher,
    )

    await listener.authenticate(_request_event(session_id))

    assert storage.get_token() is None
    deauthenticated = [
        event for event in dispatcher.events if isinstance(event, TokenDeauthenticatedEvent)
    ]
    (event,) = deauthenticated
    assert event.get_original_token() is switched
    assert event.get_reason() == "the user has changed"


async def test_a_switch_token_whose_original_carries_no_user_refreshes_only_its_own() -> None:
    """A switch standing on a token about nobody skips the recursion and reloads its own user."""
    provider = _PerUserProvider()
    switched = SwitchUserToken(InMemoryUser("ada"), "main", ("ROLE_USER",), NullToken())
    session_storage = MemorySessionStorage()
    session_id = await _session_holding(session_storage, _MAIN_KEY, switched)
    storage = TokenStorage()
    listener = _listener((provider,), session_storage=session_storage, storage=storage)

    await listener.authenticate(_request_event(session_id))

    stored = storage.get_token()
    assert stored is switched
    assert list(provider.refreshed_users) == ["ada"]
