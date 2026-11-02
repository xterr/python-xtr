from __future__ import annotations

import pytest

from tests.support.smtp_auth_exchange import authenticate
from xtr_mailer.exception import InvalidArgumentError
from xtr_mailer.transport.smtp.auth import AuthenticatorInterface, CramMd5Authenticator

pytestmark = pytest.mark.anyio

#: The challenge ``<0123456789.01234567@example.org>``.
_CHALLENGE = "334 PDAxMjM0NTY3ODkuMDEyMzQ1NjdAZXhhbXBsZS5vcmc+"


def test_it_is_the_cram_md5_mechanism() -> None:
    authenticator = CramMd5Authenticator()

    assert isinstance(authenticator, AuthenticatorInterface)
    assert authenticator.get_auth_keyword() == "CRAM-MD5"


async def test_it_answers_the_challenge_with_the_user_and_a_keyed_digest() -> None:
    assert await authenticate(CramMd5Authenticator(), [_CHALLENGE]) == [
        "AUTH CRAM-MD5",
        "dGVzdHVzZXIgMzU5OGQ3NWFiMzFlOWIxNGQyODI0ODE1MjExMGUyZDA=",
    ]


async def test_a_password_longer_than_a_block_is_hashed_into_the_key() -> None:
    lines = await authenticate(CramMd5Authenticator(), [_CHALLENGE], password="x" * 80)

    assert lines[1] == "dGVzdHVzZXIgYmM4MjY1YWRkZWMwNjkyMzIxODkzZWVmNGJiYzdlZWM="


@pytest.mark.parametrize(
    "challenge", ["334 !!not base64!!", "334", "334 PDAx=MjM", "334-a\r\n334 b"]
)
async def test_a_malformed_challenge_is_still_answered(challenge: str) -> None:
    lines = await authenticate(CramMd5Authenticator(), [challenge])

    assert lines[0] == "AUTH CRAM-MD5"
    assert len(lines) == 2


async def test_an_empty_password_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match=r"^A non-empty secret is required\.$"):
        _ = await authenticate(CramMd5Authenticator(), [_CHALLENGE], password="")
