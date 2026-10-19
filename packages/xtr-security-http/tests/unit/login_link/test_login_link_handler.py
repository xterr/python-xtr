"""The login-link handler: a link signed, and a link followed back."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from urllib.parse import parse_qsl, urlencode, urlsplit

import pytest
from xtr_clock import MockClock
from xtr_security_core.exception import InvalidArgumentError
from xtr_security_core.signature.signature_hasher import SignatureHasher
from xtr_security_core.user.in_memory_user import InMemoryUser

from tests.support.messages import make_message
from tests.support.remember_me import RecordingUserProvider
from xtr_security_http._security_state import security_state_of
from xtr_security_http.exception import (
    ExpiredLoginLinkError,
    InvalidLoginLinkError,
    InvalidLoginLinkErrorInterface,
    MissingStateBagError,
)
from xtr_security_http.login_link import (
    LoginLinkDetails,
    LoginLinkHandler,
    LoginLinkHandlerInterface,
)
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_core.user.user_interface import UserInterface

pytestmark = pytest.mark.anyio

#: Where every test freezes: a moment the expiry arithmetic can be read at.
_FROZEN = "2024-04-09 12:00:00"

#: Ten minutes, the lifetime the handler's options default to.
_TEN_MINUTES = 600

#: A password a test user carries; a fixture, not a secret.
_HASHED = "hashed"

#: The password the same user changes to; still a fixture, still no secret.
_REHASHED = "rehashed"


def _frozen() -> MockClock:
    return MockClock(_FROZEN)


def _handler(
    clock: MockClock,
    user: UserInterface,
    *,
    options: dict[str, object] | None = None,
    uri_builder: Callable[[str, ServerRequestInterface | None], str] | None = None,
) -> tuple[LoginLinkHandler, RecordingUserProvider]:
    """Build the handler over a frozen clock, its user registered with the provider."""
    provider = RecordingUserProvider({user.get_user_identifier(): user})
    hasher = SignatureHasher(["password"], "a-secret", clock=clock)
    return (
        LoginLinkHandler(
            provider,
            hasher,
            {"path": "/login-link", **(options or {})},
            uri_builder=uri_builder,
            clock=clock,
        ),
        provider,
    )


def _absolute_builder(path: str, request: ServerRequestInterface | None) -> str:
    """A URI builder writing the absolute URI of a path, for a test to inject."""
    del request
    return f"https://example.com{path}"


def _request(
    query: str = "",
    *,
    method: str = "GET",
    parsed_body: object = None,
) -> ServerRequestInterface:
    """Build a request carrying a query, a method and a parsed body, as asked."""
    message = make_message(method=method, query=query, parsed_body=parsed_body)
    bag: dict[str, object] = {}
    return message.with_attribute(SecurityRequestAttributes.STATE_BAG, bag)


def _query_of(url: str) -> dict[str, str]:
    """Return the link's query parameters, parsed."""
    return dict(parse_qsl(urlsplit(url).query, keep_blank_values=True))


def _presenting(url: str, **overrides: str) -> ServerRequestInterface:
    """Build a request presenting the link ``url`` carries, tampered as asked."""
    parameters = _query_of(url)
    parameters.update(overrides)
    return _request(urlencode(parameters))


def _parked_of(request: ServerRequestInterface) -> dict[str, object]:
    """Return the attributes the request's security state carries."""
    bag = request.get_attribute(SecurityRequestAttributes.STATE_BAG)
    assert isinstance(bag, dict)
    return security_state_of(cast("dict[str, object]", bag)).attributes


async def _link_of(handler: LoginLinkHandler, user: UserInterface) -> LoginLinkDetails:
    """Mint a link for ``user``, the plain one every test starts from."""
    return await handler.create_login_link(user)


def test_the_handler_satisfies_the_interface() -> None:
    handler, _provider = _handler(_frozen(), InMemoryUser("ada", password=_HASHED))

    assert isinstance(handler, LoginLinkHandlerInterface)


async def test_create_signs_a_link_for_the_user_until_the_default_lifetime() -> None:
    clock = _frozen()
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider = _handler(clock, user)

    link = await _link_of(handler, user)

    query = _query_of(link.get_url())
    assert query["user"] == "ada"
    assert query["expires"] == str(int(clock.now().timestamp()) + _TEN_MINUTES)
    assert query["hash"] != ""
    assert link.get_expires_at().timestamp() == int(clock.now().timestamp()) + _TEN_MINUTES


async def test_create_honours_a_lifetime_override() -> None:
    clock = _frozen()
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider = _handler(clock, user)

    link = await handler.create_login_link(user, lifetime=60)

    assert _query_of(link.get_url())["expires"] == str(int(clock.now().timestamp()) + 60)


async def test_a_zero_lifetime_falls_back_to_the_configured_one() -> None:
    clock = _frozen()
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider = _handler(clock, user)

    link = await handler.create_login_link(user, lifetime=0)

    assert _query_of(link.get_url())["expires"] == str(int(clock.now().timestamp()) + _TEN_MINUTES)


async def test_create_refuses_a_malformed_parameter_name() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider = _handler(_frozen(), user)

    with pytest.raises(InvalidArgumentError, match="must match"):
        _ = await handler.create_login_link(user, parameters={"a b": "1"})


@pytest.mark.parametrize("name", ["user", "expires", "hash", "hash_parameters"])
async def test_create_refuses_each_reserved_parameter_name(name: str) -> None:
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider = _handler(_frozen(), user)

    with pytest.raises(InvalidArgumentError, match="is reserved"):
        _ = await handler.create_login_link(user, parameters={name: "1"})


async def test_create_lists_the_extra_parameters_sorted() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider = _handler(_frozen(), user)

    link = await handler.create_login_link(user, parameters={"beta": "2", "alpha": "1"})

    assert _query_of(link.get_url())["hash_parameters"] == "alpha,beta"


async def test_create_renders_parameter_values_the_way_the_hash_reads_them() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider = _handler(_frozen(), user)

    link = await handler.create_login_link(user, parameters={"flag": True, "count": 5})

    query = _query_of(link.get_url())
    assert query["flag"] == "1"
    assert query["count"] == "5"
    assert await handler.consume_login_link(_presenting(link.get_url())) is user


async def test_create_builds_a_path_only_url_by_default() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider = _handler(_frozen(), user)

    link = await _link_of(handler, user)

    assert link.get_url().startswith("/login-link?")


async def test_create_builds_the_url_through_the_injected_builder() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider = _handler(_frozen(), user, uri_builder=_absolute_builder)

    link = await _link_of(handler, user)

    assert link.get_url().startswith("https://example.com/login-link?")


async def test_create_hands_the_request_to_the_builder() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    built: list[tuple[str, object]] = []

    def recording_builder(path: str, request: ServerRequestInterface | None) -> str:
        built.append((path, request))
        return path

    handler, _provider = _handler(_frozen(), user, uri_builder=recording_builder)
    request = _request()

    _ = await handler.create_login_link(user, request)

    assert built == [("/login-link", request)]


async def test_create_returns_an_absolute_url_path_as_it_is() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    built: list[object] = []

    def recording_builder(path: str, request: ServerRequestInterface | None) -> str:
        del request
        built.append(path)
        return path

    handler, _provider = _handler(
        _frozen(),
        user,
        options={"path": "https://links.example.com/login"},
        uri_builder=recording_builder,
    )

    link = await _link_of(handler, user)

    assert link.get_url().startswith("https://links.example.com/login?")
    assert built == []


async def test_create_refuses_a_path_that_is_a_route_name() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider = _handler(_frozen(), user, options={"path": "login_link"})

    with pytest.raises(InvalidArgumentError, match="route names are not supported"):
        _ = await _link_of(handler, user)


def test_the_handler_refuses_a_route_name_option() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    provider = RecordingUserProvider({"ada": user})
    hasher = SignatureHasher(["password"], "a-secret")

    with pytest.raises(InvalidArgumentError, match='"route_name" option is not supported'):
        _ = LoginLinkHandler(provider, hasher, {"route_name": "app_login_link"})


def test_the_handler_requires_a_path_option() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    provider = RecordingUserProvider({"ada": user})
    hasher = SignatureHasher(["password"], "a-secret")

    with pytest.raises(InvalidArgumentError, match="requires a path option"):
        _ = LoginLinkHandler(provider, hasher, {})


async def test_consume_returns_the_user_a_valid_link_signs_in() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    handler, provider = _handler(_frozen(), user)
    link = await _link_of(handler, user)

    signed_in = await handler.consume_login_link(_presenting(link.get_url()))

    assert signed_in is user
    assert provider.asked == ["ada"]


async def test_consume_parks_the_extra_parameters_on_the_request() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider = _handler(_frozen(), user)
    link = await handler.create_login_link(user, parameters={"beta": "2", "alpha": "1"})
    request = _presenting(link.get_url())

    _ = await handler.consume_login_link(request)

    assert _parked_of(request)[SecurityRequestAttributes.LOGIN_LINK_PARAMETERS] == {
        "alpha": "1",
        "beta": "2",
    }


async def test_consume_parks_an_empty_mapping_when_the_link_carried_no_extras() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider = _handler(_frozen(), user)
    link = await _link_of(handler, user)
    request = _presenting(link.get_url())

    _ = await handler.consume_login_link(request)

    assert _parked_of(request)[SecurityRequestAttributes.LOGIN_LINK_PARAMETERS] == {}


async def test_consume_refuses_a_request_with_no_user_parameter() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider = _handler(_frozen(), user)

    with pytest.raises(InvalidLoginLinkError, match='Missing "user" parameter'):
        _ = await handler.consume_login_link(_request())


async def test_consume_refuses_a_non_string_user_parameter() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider = _handler(_frozen(), user)

    with pytest.raises(InvalidLoginLinkError, match='Invalid "user" parameter'):
        _ = await handler.consume_login_link(
            _request(method="POST", parsed_body={"user": ["ada", "grace"]}),
        )


async def test_consume_refuses_a_request_with_no_hash_parameter() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider = _handler(_frozen(), user)

    with pytest.raises(InvalidLoginLinkError, match='Missing "hash" parameter'):
        _ = await handler.consume_login_link(_request("user=ada"))


async def test_consume_refuses_a_non_string_hash_parameter() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider = _handler(_frozen(), user)

    with pytest.raises(InvalidLoginLinkError, match='Invalid "hash" parameter'):
        _ = await handler.consume_login_link(
            _request(method="POST", parsed_body={"user": "ada", "hash": ["one", "two"]}),
        )


async def test_consume_refuses_a_request_with_no_expires_parameter() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider = _handler(_frozen(), user)

    with pytest.raises(InvalidLoginLinkError, match='Missing "expires" parameter'):
        _ = await handler.consume_login_link(_request("user=ada&hash=one"))


async def test_consume_refuses_a_non_numeric_expires_parameter() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider = _handler(_frozen(), user)

    with pytest.raises(InvalidLoginLinkError, match='Invalid "expires" parameter'):
        _ = await handler.consume_login_link(_request("user=ada&hash=one&expires=soon"))


async def test_consume_refuses_a_non_string_hash_parameters_parameter() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider = _handler(_frozen(), user)

    with pytest.raises(InvalidLoginLinkError, match='Invalid "hash_parameters" parameter'):
        _ = await handler.consume_login_link(
            _request(
                method="POST",
                parsed_body={
                    "user": "ada",
                    "hash": "one",
                    "expires": "1",
                    "hash_parameters": ["a", "b"],
                },
            ),
        )


async def test_consume_refuses_a_malformed_extra_parameter_name() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider = _handler(_frozen(), user)

    with pytest.raises(InvalidLoginLinkError, match='Invalid "a:b" parameter'):
        _ = await handler.consume_login_link(
            _request("user=ada&hash=one&expires=1&hash_parameters=a%3Ab"),
        )


async def test_consume_refuses_a_missing_extra_parameter() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider = _handler(_frozen(), user)

    with pytest.raises(InvalidLoginLinkError, match='Missing "alpha" parameter'):
        _ = await handler.consume_login_link(
            _request("user=ada&hash=one&expires=1&hash_parameters=alpha"),
        )


async def test_consume_refuses_a_non_string_extra_parameter() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider = _handler(_frozen(), user)

    with pytest.raises(InvalidLoginLinkError, match='Invalid "alpha" parameter'):
        _ = await handler.consume_login_link(
            _request(
                method="POST",
                parsed_body={
                    "user": "ada",
                    "hash": "one",
                    "expires": "1",
                    "hash_parameters": "alpha",
                    "alpha": ["1", "2"],
                },
            ),
        )


async def test_consume_refuses_a_tampered_hash() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider = _handler(_frozen(), user)
    link = await _link_of(handler, user)

    with pytest.raises(InvalidLoginLinkError, match="Invalid or expired login link"):
        _ = await handler.consume_login_link(_presenting(link.get_url(), hash="tampered"))


async def test_consume_refuses_a_tampered_extra_parameter() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider = _handler(_frozen(), user)
    link = await handler.create_login_link(user, parameters={"alpha": "1"})

    with pytest.raises(InvalidLoginLinkError, match="Invalid or expired login link"):
        _ = await handler.consume_login_link(_presenting(link.get_url(), alpha="2"))


async def test_consume_refuses_an_expired_link() -> None:
    clock = _frozen()
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider = _handler(clock, user)
    link = await _link_of(handler, user)
    clock.sleep(_TEN_MINUTES + 1)

    with pytest.raises(ExpiredLoginLinkError, match="Login link has expired"):
        _ = await handler.consume_login_link(_presenting(link.get_url()))


async def test_consume_refuses_an_unknown_user() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    handler, provider = _handler(_frozen(), user)
    link = await _link_of(handler, user)
    provider.users.clear()

    with pytest.raises(InvalidLoginLinkError, match="User not found"):
        _ = await handler.consume_login_link(_presenting(link.get_url()))


async def test_consume_refuses_a_link_whose_user_changed_their_password() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    handler, provider = _handler(_frozen(), user)
    link = await _link_of(handler, user)
    provider.users["ada"] = InMemoryUser("ada", password=_REHASHED)

    with pytest.raises(InvalidLoginLinkError, match="Invalid or expired login link"):
        _ = await handler.consume_login_link(_presenting(link.get_url()))


async def test_consume_checks_the_hash_before_loading_the_user() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    handler, provider = _handler(_frozen(), user)
    link = await _link_of(handler, user)
    provider.users.clear()

    with pytest.raises(InvalidLoginLinkError, match="Invalid or expired login link"):
        _ = await handler.consume_login_link(_presenting(link.get_url(), hash="tampered"))

    assert provider.asked == []


async def test_consume_reads_the_link_from_the_body_of_a_post() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider = _handler(_frozen(), user)
    link = await _link_of(handler, user)
    request = _request(method="POST", parsed_body=_query_of(link.get_url()))

    assert await handler.consume_login_link(request) is user


async def test_consume_requires_a_state_bag_to_park_the_parameters_on() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider = _handler(_frozen(), user)
    link = await _link_of(handler, user)
    request = make_message(query=urlsplit(link.get_url()).query)

    with pytest.raises(MissingStateBagError):
        _ = await handler.consume_login_link(request)


async def test_the_refusals_wear_the_marker_the_flow_catches() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider = _handler(_frozen(), user)

    with pytest.raises(InvalidLoginLinkErrorInterface):
        _ = await handler.consume_login_link(_request())
