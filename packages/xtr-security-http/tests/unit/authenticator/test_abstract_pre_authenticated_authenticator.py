"""The pre-authenticated base: the shape every server-vouched login shares."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override
from xtr_security_core.authentication.token.pre_authenticated_token import PreAuthenticatedToken
from xtr_security_core.exception import BadCredentialsError
from xtr_security_core.user.in_memory_user import InMemoryUser
from xtr_security_core.user.in_memory_user_provider import InMemoryUserProvider

from tests.support.messages import make_message
from tests.support.recording_logger import RecordingLogger
from xtr_security_http.authenticator.abstract_pre_authenticated_authenticator import (
    AbstractPreAuthenticatedAuthenticator,
)
from xtr_security_http.authenticator.debug.unsupported_reasons import UnsupportedReasons
from xtr_security_http.authenticator.passport.badge.pre_authenticated_user_badge import (
    PreAuthenticatedUserBadge,
)
from xtr_security_http.authenticator.token.post_authentication_token import (
    PostAuthenticationToken,
)
from xtr_security_http.event.check_passport_event import CheckPassportEvent
from xtr_security_http.event_listener.user_checker_listener import UserCheckerListener
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_logging_contracts import LoggerInterface
    from xtr_security_core.authentication.token.storage.token_storage_interface import (
        TokenStorageInterface,
    )
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.user.user_interface import UserInterface

    from xtr_security_http.authenticator.passport.passport import Passport

pytestmark = pytest.mark.anyio

_ADA = InMemoryUser("ada", roles=("ROLE_USER",))
_BOB = InMemoryUser("bob", roles=("ROLE_ADMIN",))


@final
class _RecordingTokenStorage:
    """A token storage that answers what it was built with, recording writes."""

    __slots__ = ("_token", "sets")

    def __init__(self, token: TokenInterface | None = None) -> None:
        self._token = token
        self.sets: list[TokenInterface | None] = []

    def get_token(self) -> TokenInterface | None:
        """Return the token this storage was built with, or last given."""
        return self._token

    def set_token(self, token: TokenInterface | None) -> None:
        """Record ``token`` as the current one."""
        self._token = token
        self.sets.append(token)


@final
class _PresetAuthenticator(AbstractPreAuthenticatedAuthenticator):
    """Answers extraction from a preset value, recording the requests it read."""

    __slots__ = ("answer", "read")

    def __init__(
        self,
        storage: TokenStorageInterface,
        answer: str | BadCredentialsError | None,
        *,
        firewall_name: str = "main",
        logger: LoggerInterface | None = None,
    ) -> None:
        super().__init__(InMemoryUserProvider({"ada": _ADA}), storage, firewall_name, logger)
        self.answer = answer
        self.read: list[ServerRequestInterface] = []

    @override
    def extract_username(self, request: ServerRequestInterface) -> str | None:
        """Answer the preset value, or raise it when it is an error."""
        self.read.append(request)
        if isinstance(self.answer, BadCredentialsError):
            raise self.answer
        return self.answer


@final
class _RefusingChecker:
    """A user checker that fails the test when the account check runs."""

    __slots__ = ("ran",)

    def __init__(self) -> None:
        self.ran = 0

    async def check_pre_auth(self, user: UserInterface) -> None:
        """Refuse: the pre-authenticated passport must keep this call away."""
        del user
        self.ran += 1
        raise AssertionError("the pre-authenticated passport must skip the pre-auth check")

    async def check_post_auth(
        self,
        user: UserInterface,
        token: TokenInterface | None = None,
    ) -> None:
        """Refuse: this test never reaches the post-authentication check."""
        del user, token
        raise AssertionError("this test never reaches the post-authentication check")


def _request(reasons: UnsupportedReasons | None = None) -> ServerRequestInterface:
    """Build a request, carrying a reasons collector when one is asked for."""
    message = make_message()
    if reasons is not None:
        message = message.with_attribute(SecurityRequestAttributes.UNSUPPORTED_REASONS, reasons)
    return message


def test_supports_answers_true_for_a_request_that_names_a_user() -> None:
    authenticator = _PresetAuthenticator(_RecordingTokenStorage(), "ada")

    assert authenticator.supports(_request()) is True


def test_supports_explains_a_request_that_names_no_user() -> None:
    reasons = UnsupportedReasons()
    authenticator = _PresetAuthenticator(_RecordingTokenStorage(), None)

    supported = authenticator.supports(_request(reasons))

    assert supported is False
    assert reasons.all() == ("no user identifier was found in the request",)


def test_supports_explains_a_refused_reading_and_clears_the_token() -> None:
    reasons = UnsupportedReasons()
    storage = _RecordingTokenStorage(PreAuthenticatedToken(_ADA, "main"))
    refusal = BadCredentialsError("The certificate the request presented is expired.")
    authenticator = _PresetAuthenticator(storage, refusal)

    supported = authenticator.supports(_request(reasons))

    assert supported is False
    assert reasons.all() == ("The certificate the request presented is expired.",)
    assert storage.sets == [None]


def test_supports_skips_a_user_the_firewall_already_settled() -> None:
    reasons = UnsupportedReasons()
    logger = RecordingLogger()
    storage = _RecordingTokenStorage(PreAuthenticatedToken(_ADA, "main"))
    authenticator = _PresetAuthenticator(storage, "ada", logger=logger)

    supported = authenticator.supports(_request(reasons))

    assert supported is False
    assert reasons.all() == (
        'the user "ada" already has a pre-authenticated token for this firewall',
    )
    assert logger.messages("debug") == [
        "Skipping pre-authenticated authenticator as the user already has an existing session.",
    ]
    assert storage.sets == []


def test_supports_leaves_another_firewalls_token_alone() -> None:
    storage = _RecordingTokenStorage(PreAuthenticatedToken(_ADA, "other"))
    authenticator = _PresetAuthenticator(storage, "ada")

    assert authenticator.supports(_request()) is True
    assert storage.sets == []


def test_supports_leaves_a_token_for_another_user_alone() -> None:
    storage = _RecordingTokenStorage(PreAuthenticatedToken(_BOB, "main"))
    authenticator = _PresetAuthenticator(storage, "ada")

    assert authenticator.supports(_request()) is True
    assert storage.sets == []


def test_supports_ignores_a_token_of_another_kind() -> None:
    storage = _RecordingTokenStorage(PostAuthenticationToken(_ADA, "main", ("ROLE_USER",)))
    authenticator = _PresetAuthenticator(storage, "ada")

    assert authenticator.supports(_request()) is True
    assert storage.sets == []


async def test_authenticate_builds_a_passport_that_vouches_for_itself() -> None:
    authenticator = _PresetAuthenticator(_RecordingTokenStorage(), "ada")

    passport = await authenticator.authenticate(_request())

    assert passport.has_badge(PreAuthenticatedUserBadge)
    assert await passport.get_user() is _ADA


async def test_authenticate_reads_the_request_again() -> None:
    authenticator = _PresetAuthenticator(_RecordingTokenStorage(), "ada")
    request = _request()
    _ = authenticator.supports(request)

    passport = await authenticator.authenticate(request)

    assert authenticator.read == [request, request]
    assert await passport.get_user() is _ADA


async def test_authenticate_refuses_a_request_that_no_longer_names_a_user() -> None:
    authenticator = _PresetAuthenticator(_RecordingTokenStorage(), None)

    with pytest.raises(BadCredentialsError) as raised:
        _ = await authenticator.authenticate(_request())

    assert str(raised.value) == "No pre-authenticated user identifier was found in the request."


async def test_create_token_mints_a_pre_authenticated_token() -> None:
    authenticator = _PresetAuthenticator(_RecordingTokenStorage(), "ada")
    passport = await authenticator.authenticate(_request())

    token = await authenticator.create_token(passport, "main")

    assert isinstance(token, PreAuthenticatedToken)
    assert token.get_user_identifier() == "ada"
    assert token.get_firewall_name() == "main"
    assert tuple(token.get_role_names()) == ("ROLE_USER",)


async def test_a_failure_clears_the_firewalls_token_and_answers_nothing() -> None:
    logger = RecordingLogger()
    storage = _RecordingTokenStorage(PreAuthenticatedToken(_ADA, "main"))
    authenticator = _PresetAuthenticator(storage, "ada", logger=logger)

    response = await authenticator.on_authentication_failure(
        _request(),
        BadCredentialsError("The certificate the request presented is expired."),
    )

    assert response is None
    assert storage.sets == [None]
    assert logger.messages("info") == ["Cleared pre-authenticated token due to an exception."]


async def test_a_failure_leaves_another_firewalls_token_alone() -> None:
    storage = _RecordingTokenStorage(PreAuthenticatedToken(_ADA, "other"))
    authenticator = _PresetAuthenticator(storage, "ada")

    response = await authenticator.on_authentication_failure(
        _request(),
        BadCredentialsError("The certificate the request presented is expired."),
    )

    assert response is None
    assert storage.sets == []


def test_the_login_reports_itself_interactive() -> None:
    authenticator = _PresetAuthenticator(_RecordingTokenStorage(), "ada")

    assert authenticator.is_interactive() is True


async def test_the_passport_skips_the_pre_authentication_account_check() -> None:
    checker = _RefusingChecker()
    authenticator = _PresetAuthenticator(_RecordingTokenStorage(), "ada")
    passport: Passport = await authenticator.authenticate(_request())

    await UserCheckerListener(checker).pre_check_credentials(
        CheckPassportEvent(authenticator, passport, _request()),
    )

    assert checker.ran == 0
