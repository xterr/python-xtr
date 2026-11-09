"""The last login attempt's error and username, read off one request."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from xtr_http_foundation import MemorySessionStorage, Session
from xtr_security_core.exception import BadCredentialsError, TooManyLoginAttemptsAuthenticationError

from tests.support.messages import make_message
from xtr_security_http._security_state import security_state_of
from xtr_security_http.authentication.authentication_utils import AuthenticationUtils
from xtr_security_http.security_request_attributes import SecurityRequestAttributes
from xtr_security_http.session.authentication_error_serializer import (
    authentication_error_to_session,
)

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

pytestmark = pytest.mark.anyio


def _request_with_session() -> tuple[ServerRequestInterface, Session]:
    """Build a request whose security state carries a parked session."""
    bag: dict[str, object] = {}
    message = make_message().with_attribute(SecurityRequestAttributes.STATE_BAG, bag)
    session = Session(MemorySessionStorage())
    security_state_of(bag).attributes[SecurityRequestAttributes.SESSION] = session
    return message, session


async def test_the_error_is_read_off_the_request_state_first() -> None:
    bag: dict[str, object] = {}
    message = make_message().with_attribute(SecurityRequestAttributes.STATE_BAG, bag)
    session = Session(MemorySessionStorage())
    security_state_of(bag).attributes[SecurityRequestAttributes.SESSION] = session
    parked = BadCredentialsError("The request state's own error.")
    await session.set(
        SecurityRequestAttributes.AUTHENTICATION_ERROR,
        authentication_error_to_session(BadCredentialsError("kept")),
    )
    security_state_of(bag).attributes[SecurityRequestAttributes.AUTHENTICATION_ERROR] = parked

    assert await AuthenticationUtils(message).get_last_authentication_error() is parked


async def test_the_error_is_rebuilt_off_the_session_and_removed_with_it() -> None:
    message, session = _request_with_session()
    kept = BadCredentialsError("the password of alice did not match")
    await session.set(
        SecurityRequestAttributes.AUTHENTICATION_ERROR,
        authentication_error_to_session(kept),
    )

    rebuilt = await AuthenticationUtils(message).get_last_authentication_error()

    assert type(rebuilt) is BadCredentialsError
    assert rebuilt.get_message_key() == "Invalid credentials."
    assert str(rebuilt) == "Invalid credentials."
    assert await session.has(SecurityRequestAttributes.AUTHENTICATION_ERROR) is False


async def test_the_error_is_rebuilt_with_the_data_the_session_kept() -> None:
    message, session = _request_with_session()
    await session.set(
        SecurityRequestAttributes.AUTHENTICATION_ERROR,
        authentication_error_to_session(TooManyLoginAttemptsAuthenticationError(5)),
    )

    rebuilt = await AuthenticationUtils(message).get_last_authentication_error()

    assert isinstance(rebuilt, TooManyLoginAttemptsAuthenticationError)
    assert rebuilt.threshold == 5
    assert rebuilt.get_message_data() == {"%minutes%": 5, "%count%": 5}


async def test_the_error_stays_on_the_session_when_clearing_is_refused() -> None:
    message, session = _request_with_session()
    await session.set(
        SecurityRequestAttributes.AUTHENTICATION_ERROR,
        authentication_error_to_session(BadCredentialsError("kept")),
    )

    rebuilt = await AuthenticationUtils(message).get_last_authentication_error(clear_session=False)

    assert type(rebuilt) is BadCredentialsError
    assert await session.has(SecurityRequestAttributes.AUTHENTICATION_ERROR) is True


async def test_no_kept_error_answers_none() -> None:
    message, _session = _request_with_session()

    assert await AuthenticationUtils(message).get_last_authentication_error() is None


async def test_a_kept_value_that_is_no_error_answers_none() -> None:
    message, session = _request_with_session()
    await session.set(SecurityRequestAttributes.AUTHENTICATION_ERROR, "not an error")

    assert await AuthenticationUtils(message).get_last_authentication_error() is None


async def test_a_live_error_a_session_kept_is_no_envelope_and_answers_none() -> None:
    message, session = _request_with_session()
    await session.set(SecurityRequestAttributes.AUTHENTICATION_ERROR, BadCredentialsError("live"))

    assert await AuthenticationUtils(message).get_last_authentication_error() is None


async def test_the_username_is_read_off_the_request_state_first() -> None:
    bag: dict[str, object] = {}
    message = make_message().with_attribute(SecurityRequestAttributes.STATE_BAG, bag)
    security_state_of(bag).attributes[SecurityRequestAttributes.LAST_USERNAME] = "alice"

    assert await AuthenticationUtils(message).get_last_username() == "alice"


async def test_the_username_is_read_off_the_session() -> None:
    message, session = _request_with_session()
    await session.set(SecurityRequestAttributes.LAST_USERNAME, "alice")

    assert await AuthenticationUtils(message).get_last_username() == "alice"


async def test_no_kept_username_answers_the_empty_string() -> None:
    message, _session = _request_with_session()

    assert await AuthenticationUtils(message).get_last_username() == ""


async def test_the_re_authentication_attribute_is_read_off_the_request_first() -> None:
    message, session = _request_with_session()
    await session.set(SecurityRequestAttributes.RE_AUTHENTICATION_ATTRIBUTE, "session")
    asked = message.with_attribute(SecurityRequestAttributes.RE_AUTHENTICATION_ATTRIBUTE, "request")

    assert await AuthenticationUtils(asked).get_re_authentication_attribute() == "request"


async def test_the_re_authentication_attribute_is_read_off_the_session() -> None:
    message, session = _request_with_session()
    await session.set(SecurityRequestAttributes.RE_AUTHENTICATION_ATTRIBUTE, "request")

    assert await AuthenticationUtils(message).get_re_authentication_attribute() == "request"


async def test_no_re_authentication_attribute_answers_none() -> None:
    message, _session = _request_with_session()

    assert await AuthenticationUtils(message).get_re_authentication_attribute() is None


async def test_a_request_no_stateful_machinery_ran_for_reads_as_keeping_nothing() -> None:
    message = make_message()
    utils = AuthenticationUtils(message)

    assert await utils.get_last_authentication_error() is None
    assert await utils.get_last_username() == ""
    assert await utils.get_re_authentication_attribute() is None


@final
class _NotAnError:
    """A value a mis-keyed session could keep under the error's key."""


async def test_a_state_bag_that_is_no_mapping_reads_as_keeping_nothing() -> None:
    message = make_message().with_attribute(SecurityRequestAttributes.STATE_BAG, _NotAnError())
    utils = AuthenticationUtils(message)

    assert await utils.get_last_authentication_error() is None
    assert await utils.get_last_username() == ""
