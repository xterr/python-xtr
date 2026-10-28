"""The chain step that switches the user a request asks to impersonate."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar, final

import pytest
from xtr_http_kernel import RequestEvent
from xtr_http_kernel.bridge import ResponseFactory, StarletteHttpFactory
from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.authentication.token.switch_user_token import SwitchUserToken
from xtr_security_core.exception import (
    AccessDeniedError,
    AuthenticationCredentialsNotFoundError,
    InvalidArgumentError,
    UserNotFoundError,
)
from xtr_security_core.user.in_memory_user import InMemoryUser
from xtr_security_csrf.csrf_token import CsrfToken

from tests.support.messages import make_message
from xtr_security_http._security_state import security_state_of
from xtr_security_http.authenticator.token.post_authentication_token import (
    PostAuthenticationToken,
)
from xtr_security_http.decorator.firewall_listener_order import firewall_listener_order_of
from xtr_security_http.event.switch_user_event import SwitchUserEvent
from xtr_security_http.firewall.authenticator_manager_listener import (
    AuthenticatorManagerListener,
)
from xtr_security_http.firewall.firewall_listener_interface import FirewallListenerInterface
from xtr_security_http.firewall.switch_user_listener import SwitchUserListener
from xtr_security_http.http_utils import HttpUtils
from xtr_security_http.security_events import SecurityEvents
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.authorization.access_decision import AccessDecision
    from xtr_security_core.user.user_interface import UserInterface
    from xtr_security_csrf.csrf_token_manager_interface import CsrfTokenManagerInterface

pytestmark = pytest.mark.anyio

_EventT = TypeVar("_EventT")


@final
class _DecidingManager:
    """Answers what it was built to, recording every decision it was asked."""

    __slots__ = ("_granted", "asks")

    def __init__(self, granted: bool = True) -> None:
        self._granted = granted
        self.asks: list[tuple[TokenInterface, tuple[object, ...], object]] = []

    async def decide(
        self,
        token: TokenInterface,
        attributes: Sequence[object],
        subject: object = None,
        access_decision: AccessDecision | None = None,
    ) -> bool:
        """Record the ask, and answer the verdict this manager was built with."""
        self.asks.append((token, tuple(attributes), subject))
        if access_decision is not None:
            access_decision.is_granted = self._granted
        return self._granted


@final
class _RecordingProvider:
    """Loads and reloads users from a fixed set, recording every ask."""

    __slots__ = ("_users", "loaded", "refreshed")

    def __init__(self, users: Mapping[str, InMemoryUser]) -> None:
        self._users = dict(users)
        self.loaded: list[str] = []
        self.refreshed: list[str] = []

    async def load_user_by_identifier(self, identifier: str) -> InMemoryUser:
        """Record the ask, and answer the user the set holds, or nobody."""
        self.loaded.append(identifier)
        user = self._users.get(identifier)
        if user is None:
            raise UserNotFoundError(identifier)
        return user

    async def refresh_user(self, user: UserInterface) -> InMemoryUser:
        """Record the ask, and answer the user the set holds, or nobody."""
        self.refreshed.append(user.get_user_identifier())
        stored = self._users.get(user.get_user_identifier())
        if stored is None:
            raise UserNotFoundError(user.get_user_identifier())
        return stored

    def supports_class(self, user_class: type) -> bool:
        """Tell whether ``user_class`` is the in-memory user."""
        return issubclass(user_class, InMemoryUser)


@final
class _RecordingChecker:
    """Records the users the account checks clear."""

    __slots__ = ("checked",)

    def __init__(self) -> None:
        self.checked: list[tuple[UserInterface, TokenInterface | None]] = []

    async def check_pre_auth(self, user: UserInterface) -> None:
        """Record nothing: the switch runs the post-authentication check only."""
        del user

    async def check_post_auth(
        self,
        user: UserInterface,
        token: TokenInterface | None = None,
    ) -> None:
        """Record the user and the token the switch settled on."""
        self.checked.append((user, token))


@final
class _NamedDispatcher:
    """Records every event it dispatches, under the name it was dispatched under."""

    __slots__ = ("dispatched",)

    def __init__(self) -> None:
        self.dispatched: list[tuple[object, str | type | None]] = []

    async def dispatch(
        self,
        event: _EventT,
        event_name: str | type | None = None,
    ) -> _EventT:
        """Record the event with its name, and answer it unchanged."""
        self.dispatched.append((event, event_name))
        return event


@final
class _ReplacingDispatcher:
    """Announces the switch, then replaces the token the event carries."""

    __slots__ = ("replacement",)

    def __init__(self, replacement: TokenInterface) -> None:
        self.replacement = replacement

    async def dispatch(
        self,
        event: _EventT,
        event_name: str | type | None = None,
    ) -> _EventT:
        """Replace the token a switch event carries, and answer it."""
        del event_name
        if isinstance(event, SwitchUserEvent):
            event.set_token(self.replacement)
        return event


@final
class _RecordingCsrfManager:
    """Vouches for what it was built to, recording every token it checked."""

    __slots__ = ("_valid", "asked")

    def __init__(self, valid: bool) -> None:
        self._valid = valid
        self.asked: list[CsrfToken] = []

    async def get_token(self, token_id: str) -> CsrfToken:
        """Mint a stand-in token under ``token_id``."""
        return CsrfToken(token_id, "minted")

    async def refresh_token(self, token_id: str) -> CsrfToken:
        """Mint a fresh stand-in token under ``token_id``."""
        return CsrfToken(token_id, "minted")

    async def remove_token(self, token_id: str) -> str | None:
        """Answer that nothing was stored under ``token_id``."""
        del token_id
        return None

    async def is_token_valid(self, token: CsrfToken) -> bool:
        """Record the token, and answer the verdict this manager was built with."""
        self.asked.append(token)
        return self._valid


def _listener(  # noqa: PLR0913 -- a test builder, naming every part of a listener it can shape
    storage: TokenStorage,
    provider: _RecordingProvider,
    *,
    manager: _DecidingManager | None = None,
    checker: _RecordingChecker | None = None,
    dispatcher: EventDispatcherInterface | None = None,
    csrf_token_manager: CsrfTokenManagerInterface | None = None,
    stateless: bool = False,
    path: str | None = None,
    username_parameter: str = "_switch_user",
    csrf_parameter: str = "_csrf_token",
    csrf_token_id: str = "switch_user",  # noqa: S107 -- a token id in a test, not a credential
) -> SwitchUserListener:
    return SwitchUserListener(
        storage,
        provider,
        checker or _RecordingChecker(),
        "main",
        manager or _DecidingManager(),
        StarletteHttpFactory(),
        HttpUtils(ResponseFactory()),
        dispatcher=dispatcher,
        stateless=stateless,
        path=path,
        csrf_token_manager=csrf_token_manager,
        username_parameter=username_parameter,
        csrf_parameter=csrf_parameter,
        csrf_token_id=csrf_token_id,
    )


def _asked(request: ServerRequestInterface, bag: dict[str, object]) -> ServerRequestInterface:
    """Return ``request`` carrying the event's state bag, as the chain's caller asks about it."""
    return request.with_attribute(SecurityRequestAttributes.STATE_BAG, bag)


def _admin_token() -> PostAuthenticationToken:
    return PostAuthenticationToken(InMemoryUser("admin"), "main", ())


def _switched_token(original: TokenInterface, identifier: str = "ada") -> SwitchUserToken:
    return SwitchUserToken(
        InMemoryUser(identifier),
        "main",
        ("ROLE_USER",),
        original,
        "https://example.com/",
    )


async def _switch(
    listener: SwitchUserListener,
    request: ServerRequestInterface,
    bag: dict[str, object],
) -> RequestEvent:
    """Run the supports pass and the authenticate pass the chain runs, over one request."""
    assert await listener.supports(_asked(request, bag)) is True
    event = RequestEvent(request, bag)
    await listener.authenticate(event)
    return event


def test_it_satisfies_the_interface() -> None:
    storage = TokenStorage()
    assert isinstance(
        _listener(storage, _RecordingProvider({})),
        FirewallListenerInterface,
    )


def test_the_step_runs_at_the_default_priority_ordered_after_the_manager() -> None:
    """Tied with the authentication step, and declared to run after it."""
    assert SwitchUserListener.get_priority() == 0
    order = firewall_listener_order_of(SwitchUserListener)
    assert order is not None
    assert order.after == (AuthenticatorManagerListener,)
    assert order.before == ()


def test_an_empty_firewall_name_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = SwitchUserListener(
            TokenStorage(),
            _RecordingProvider({}),
            _RecordingChecker(),
            "",
            _DecidingManager(),
            StarletteHttpFactory(),
            HttpUtils(ResponseFactory()),
        )


async def test_supports_answers_true_for_a_request_carrying_the_parameter_in_its_query() -> None:
    listener = _listener(TokenStorage(), _RecordingProvider({}))

    assert await listener.supports(_asked(make_message(query="_switch_user=ada"), {})) is True


async def test_supports_reads_the_body_of_an_unsafe_request() -> None:
    listener = _listener(TokenStorage(), _RecordingProvider({}))
    request = make_message(method="POST", parsed_body={"_switch_user": "ada"})

    assert await listener.supports(_asked(request, {})) is True


async def test_supports_falls_back_to_the_header_of_the_same_name() -> None:
    listener = _listener(TokenStorage(), _RecordingProvider({}))
    request = make_message(headers={"_switch_user": "ada"})

    assert await listener.supports(_asked(request, {})) is True


async def test_supports_refuses_a_request_without_the_parameter() -> None:
    listener = _listener(TokenStorage(), _RecordingProvider({}))

    assert await listener.supports(_asked(make_message(), {})) is False


async def test_a_non_text_parameter_reads_as_no_username() -> None:
    listener = _listener(TokenStorage(), _RecordingProvider({}))
    request = make_message(method="POST", parsed_body={"_switch_user": ["not", "text"]})

    assert await listener.supports(_asked(request, {})) is False


async def test_supports_parks_the_username_on_the_requests_security_state() -> None:
    bag: dict[str, object] = {}
    _ = await _listener(TokenStorage(), _RecordingProvider({})).supports(
        _asked(make_message(query="_switch_user=ada"), bag),
    )

    assert (
        security_state_of(bag).attributes[SecurityRequestAttributes.SWITCH_USER_USERNAME] == "ada"
    )


async def test_supports_on_a_dedicated_path_refuses_a_request_elsewhere() -> None:
    listener = _listener(TokenStorage(), _RecordingProvider({}), path="/switch")
    request = make_message(path="/other", query="_switch_user=ada")

    assert await listener.supports(_asked(request, {})) is False


async def test_supports_on_a_dedicated_path_reads_the_parameter_from_query_or_body() -> None:
    listener = _listener(TokenStorage(), _RecordingProvider({}), path="/switch")
    from_query = make_message(path="/switch", query="_switch_user=ada")
    from_body = make_message(method="POST", path="/switch", parsed_body={"_switch_user": "ada"})

    assert await listener.supports(_asked(from_query, {})) is True
    assert await listener.supports(_asked(from_body, {})) is True


async def test_a_granted_switch_settles_on_a_token_carrying_the_original() -> None:
    storage = TokenStorage()
    original = _admin_token()
    storage.set_token(original)
    provider = _RecordingProvider({"ada": InMemoryUser("ada", roles=("ROLE_USER",))})
    listener = _listener(storage, provider)

    event = _ = await _switch(listener, make_message(query="_switch_user=ada"), {})

    switched = storage.get_token()
    assert isinstance(switched, SwitchUserToken)
    assert switched.get_user_identifier() == "ada"
    assert switched.get_original_token() is original
    assert switched.get_firewall_name() == "main"
    assert set(switched.get_role_names()) == {"ROLE_USER"}
    assert switched.get_originated_from_uri() == "https://example.com/"
    assert event.response is not None
    assert event.response.status_code == 302
    assert event.response.headers["location"] == "https://example.com/"


async def test_the_decision_weighs_the_role_against_the_target_user() -> None:
    storage = TokenStorage()
    storage.set_token(_admin_token())
    manager = _DecidingManager()
    provider = _RecordingProvider({"ada": InMemoryUser("ada")})
    listener = _listener(storage, provider, manager=manager)

    _ = await _switch(listener, make_message(query="_switch_user=ada"), {})

    ((token, attributes, subject),) = manager.asks
    assert token.get_user_identifier() == "admin"
    assert attributes == ("ROLE_ALLOWED_TO_SWITCH",)
    assert isinstance(subject, InMemoryUser)
    assert subject.get_user_identifier() == "ada"


async def test_a_denied_decision_refuses_with_the_role_and_the_decision() -> None:
    storage = TokenStorage()
    storage.set_token(_admin_token())
    provider = _RecordingProvider({"ada": InMemoryUser("ada")})
    listener = _listener(storage, provider, manager=_DecidingManager(granted=False))

    with pytest.raises(AccessDeniedError) as caught:
        _ = await _switch(listener, make_message(query="_switch_user=ada"), {})

    error = caught.value
    assert error.attributes == ("ROLE_ALLOWED_TO_SWITCH",)
    assert error.access_decision is not None
    assert error.access_decision.is_granted is False


async def test_the_target_user_is_loaded_with_a_burned_dummy_load_beside_it() -> None:
    storage = TokenStorage()
    storage.set_token(_admin_token())
    provider = _RecordingProvider({"ada": InMemoryUser("ada")})
    listener = _listener(storage, provider)

    _ = await _switch(listener, make_message(query="_switch_user=ada"), {})

    assert provider.loaded[0] == "ada"
    assert len(provider.loaded) == 2
    # The burned identifier is unguessable and cannot name a real user.
    assert provider.loaded[1].startswith("_")
    assert len(provider.loaded[1]) == 65


async def test_an_unknown_target_burns_a_load_of_the_current_user_before_failing() -> None:
    storage = TokenStorage()
    storage.set_token(_admin_token())
    provider = _RecordingProvider({"admin": InMemoryUser("admin")})
    listener = _listener(storage, provider)

    with pytest.raises(AccessDeniedError) as caught:
        _ = await _switch(listener, make_message(query="_switch_user=nobody"), {})

    assert str(caught.value).startswith("Switch User failed:")
    assert provider.loaded == ["nobody", "admin"]


async def test_the_switch_is_announced_under_the_switch_user_name() -> None:
    storage = TokenStorage()
    storage.set_token(_admin_token())
    provider = _RecordingProvider({"ada": InMemoryUser("ada")})
    dispatcher = _NamedDispatcher()
    listener = _listener(storage, provider, dispatcher=dispatcher)

    _ = await _switch(listener, make_message(query="_switch_user=ada"), {})

    ((event, name),) = dispatcher.dispatched
    assert isinstance(event, SwitchUserEvent)
    assert name == SecurityEvents.SWITCH_USER
    assert event.get_target_user().get_user_identifier() == "ada"
    assert isinstance(event.get_token(), SwitchUserToken)


async def test_a_listener_may_replace_the_token_the_switch_settles_on() -> None:
    storage = TokenStorage()
    storage.set_token(_admin_token())
    provider = _RecordingProvider({"ada": InMemoryUser("ada")})
    replacement = PostAuthenticationToken(InMemoryUser("grace"), "main", ())
    listener = _listener(storage, provider, dispatcher=_ReplacingDispatcher(replacement))

    _ = await _switch(listener, make_message(query="_switch_user=ada"), {})

    assert storage.get_token() is replacement


async def test_the_post_authentication_check_runs_against_the_target_user() -> None:
    storage = TokenStorage()
    original = _admin_token()
    storage.set_token(original)
    checker = _RecordingChecker()
    provider = _RecordingProvider({"ada": InMemoryUser("ada")})
    listener = _listener(storage, provider, checker=checker)

    _ = await _switch(listener, make_message(query="_switch_user=ada"), {})

    ((user, token),) = checker.checked
    assert user.get_user_identifier() == "ada"
    assert token is original


async def test_a_switch_to_the_user_already_impersonated_changes_nothing() -> None:
    storage = TokenStorage()
    original = _admin_token()
    switched = _switched_token(original)
    storage.set_token(switched)
    provider = _RecordingProvider({"ada": InMemoryUser("ada")})
    listener = _listener(storage, provider)

    _ = await _switch(listener, make_message(query="_switch_user=ada"), {})

    assert storage.get_token() is switched
    assert provider.loaded == []


async def test_a_second_switch_leaves_the_first_seamlessly() -> None:
    storage = TokenStorage()
    original = _admin_token()
    storage.set_token(_switched_token(original))
    provider = _RecordingProvider(
        {"admin": InMemoryUser("admin"), "grace": InMemoryUser("grace")},
    )
    listener = _listener(storage, provider)

    _ = await _switch(listener, make_message(query="_switch_user=grace"), {})

    switched = storage.get_token()
    assert isinstance(switched, SwitchUserToken)
    assert switched.get_user_identifier() == "grace"
    assert switched.get_original_token() is original


async def test_the_redirect_strips_the_switch_parameter_from_the_address() -> None:
    storage = TokenStorage()
    storage.set_token(_admin_token())
    provider = _RecordingProvider({"ada": InMemoryUser("ada")})
    listener = _listener(storage, provider)

    event = _ = await _switch(listener, make_message(query="page=1&_switch_user=ada"), {})

    assert event.response is not None
    assert event.response.headers["location"] == "https://example.com/?page=1"


async def test_the_redirect_strips_a_leading_switch_parameter_cleanly() -> None:
    storage = TokenStorage()
    storage.set_token(_admin_token())
    provider = _RecordingProvider({"ada": InMemoryUser("ada")})
    listener = _listener(storage, provider)

    event = _ = await _switch(listener, make_message(query="_switch_user=ada&page=1"), {})

    assert event.response is not None
    assert event.response.headers["location"] == "https://example.com/?page=1"


async def test_the_redirect_strips_the_forgery_parameter_when_a_manager_is_wired() -> None:
    storage = TokenStorage()
    storage.set_token(_admin_token())
    provider = _RecordingProvider({"ada": InMemoryUser("ada")})
    listener = _listener(
        storage,
        provider,
        csrf_token_manager=_RecordingCsrfManager(valid=True),
    )

    event = _ = await _switch(
        listener,
        make_message(query="_switch_user=ada&_csrf_token=carried"),
        {},
    )

    assert event.response is not None
    assert event.response.headers["location"] == "https://example.com/"


async def test_a_stateless_step_switches_without_answering_the_request() -> None:
    storage = TokenStorage()
    storage.set_token(_admin_token())
    provider = _RecordingProvider({"ada": InMemoryUser("ada")})
    listener = _listener(storage, provider, stateless=True)

    event = _ = await _switch(listener, make_message(query="_switch_user=ada"), {})

    assert isinstance(storage.get_token(), SwitchUserToken)
    assert event.response is None


async def test_the_switch_path_honours_a_submitted_target_path() -> None:
    storage = TokenStorage()
    storage.set_token(_admin_token())
    provider = _RecordingProvider({"ada": InMemoryUser("ada")})
    listener = _listener(storage, provider, path="/switch")
    request = make_message(
        method="POST",
        path="/switch",
        parsed_body={"_switch_user": "ada", "_target_path": "/back"},
    )

    event = _ = await _switch(listener, request, {})

    assert event.response is not None
    assert event.response.headers["location"] == "/back"


async def test_the_switch_path_falls_back_to_the_root_without_a_target() -> None:
    storage = TokenStorage()
    storage.set_token(_admin_token())
    provider = _RecordingProvider({"ada": InMemoryUser("ada")})
    listener = _listener(storage, provider, path="/switch")
    request = make_message(method="POST", path="/switch", parsed_body={"_switch_user": "ada"})

    event = _ = await _switch(listener, request, {})

    assert event.response is not None
    assert event.response.headers["location"] == "/"


async def test_the_exit_value_restores_the_original_token() -> None:
    storage = TokenStorage()
    original = _admin_token()
    storage.set_token(_switched_token(original))
    provider = _RecordingProvider({"admin": InMemoryUser("admin")})
    listener = _listener(storage, provider)

    event = _ = await _switch(listener, make_message(query="_switch_user=_exit"), {})

    assert storage.get_token() is original
    assert event.response is not None
    assert event.response.headers["location"] == "https://example.com/"


async def test_the_exit_announces_the_refreshed_original_under_the_switch_user_name() -> None:
    storage = TokenStorage()
    original = _admin_token()
    storage.set_token(_switched_token(original))
    provider = _RecordingProvider({"admin": InMemoryUser("admin")})
    dispatcher = _NamedDispatcher()
    listener = _listener(storage, provider, dispatcher=dispatcher)

    _ = await _switch(listener, make_message(query="_switch_user=_exit"), {})

    assert provider.refreshed == ["admin"]
    ((event, name),) = dispatcher.dispatched
    assert isinstance(event, SwitchUserEvent)
    assert name == SecurityEvents.SWITCH_USER
    assert event.get_target_user().get_user_identifier() == "admin"
    assert event.get_token() is original


async def test_an_exit_without_a_switch_is_refused() -> None:
    storage = TokenStorage()
    storage.set_token(_admin_token())
    listener = _listener(storage, _RecordingProvider({}))

    with pytest.raises(AuthenticationCredentialsNotFoundError):
        _ = await _switch(listener, make_message(query="_switch_user=_exit"), {})


async def test_no_token_in_the_storage_is_refused() -> None:
    storage = TokenStorage()
    provider = _RecordingProvider({"ada": InMemoryUser("ada")})
    listener = _listener(storage, provider)

    with pytest.raises(AuthenticationCredentialsNotFoundError):
        _ = await _switch(listener, make_message(query="_switch_user=ada"), {})


async def test_a_wired_manager_validates_the_presented_token() -> None:
    storage = TokenStorage()
    storage.set_token(_admin_token())
    provider = _RecordingProvider({"ada": InMemoryUser("ada")})
    manager = _RecordingCsrfManager(valid=True)
    listener = _listener(storage, provider, csrf_token_manager=manager)

    _ = await _switch(listener, make_message(query="_switch_user=ada&_csrf_token=carried"), {})

    (asked,) = manager.asked
    assert asked.get_id() == "switch_user"
    assert asked.get_value() == "carried"
    assert isinstance(storage.get_token(), SwitchUserToken)


async def test_an_invalid_forgery_token_refuses_the_switch() -> None:
    storage = TokenStorage()
    storage.set_token(_admin_token())
    provider = _RecordingProvider({"ada": InMemoryUser("ada")})
    listener = _listener(
        storage,
        provider,
        csrf_token_manager=_RecordingCsrfManager(valid=False),
    )

    with pytest.raises(AccessDeniedError, match=r"Invalid CSRF token\."):
        _ = await _switch(listener, make_message(query="_switch_user=ada&_csrf_token=carried"), {})


async def test_a_missing_forgery_token_refuses_the_switch() -> None:
    storage = TokenStorage()
    storage.set_token(_admin_token())
    provider = _RecordingProvider({"ada": InMemoryUser("ada")})
    listener = _listener(
        storage,
        provider,
        csrf_token_manager=_RecordingCsrfManager(valid=True),
    )

    with pytest.raises(AccessDeniedError, match=r"Invalid CSRF token\."):
        _ = await _switch(listener, make_message(query="_switch_user=ada"), {})


async def test_the_proof_reads_the_parameter_and_id_the_listener_was_configured_with() -> None:
    storage = TokenStorage()
    storage.set_token(_admin_token())
    provider = _RecordingProvider({"ada": InMemoryUser("ada")})
    manager = _RecordingCsrfManager(valid=True)
    listener = _listener(
        storage,
        provider,
        csrf_token_manager=manager,
        csrf_parameter="proof",
        csrf_token_id="switch",  # noqa: S106 -- a token id in a test, not a credential
    )

    _ = await _switch(listener, make_message(query="_switch_user=ada&proof=carried"), {})

    (asked,) = manager.asked
    assert asked.get_id() == "switch"
    assert asked.get_value() == "carried"


async def test_authenticate_without_a_supports_pass_leaves_the_request_alone() -> None:
    storage = TokenStorage()
    original = _admin_token()
    storage.set_token(original)
    provider = _RecordingProvider({"ada": InMemoryUser("ada")})
    listener = _listener(storage, provider)

    event = RequestEvent(make_message(query="_switch_user=ada"), {})
    await listener.authenticate(event)

    assert event.response is None
    assert storage.get_token() is original
    assert provider.loaded == []
