"""``security:oidc:generate-token`` mints an OIDC access token for a user."""

from __future__ import annotations

import io
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from joserfc import jwt
from xtr_clock import MockClock
from xtr_console import ConsoleStyle

from tests.support.oidc import NOW, make_key, make_key_set
from xtr_security_http.access_token.oidc import OidcTokenGenerator
from xtr_security_http.command.oidc_token_generate_command import OidcTokenGenerateCommand

if TYPE_CHECKING:
    from joserfc.jwk import RSAKey

pytestmark = pytest.mark.anyio

_ISSUER = "https://issuer.example"
_OTHER_ISSUER = "https://other.example"
_AUDIENCE = "shop-api"

# Wide enough that the token a run prints stays on one line, so what the
# output holds can be compared with the token itself.
_WIDTH = 1000


def _style() -> tuple[ConsoleStyle, io.StringIO]:
    """A style writing to a string, so a run's output can be read back."""
    output = io.StringIO()
    style = ConsoleStyle(output, io.StringIO(), width=_WIDTH, decorated=False, interactive=False)
    return style, output


def _clock() -> MockClock:
    """A clock frozen where the OIDC test support counts from."""
    return MockClock(datetime.fromtimestamp(NOW, UTC))


def _generator(
    key: RSAKey,
    *,
    algorithms: tuple[str, ...] = ("RS256",),
    issuers: tuple[str, ...] = (_ISSUER,),
) -> OidcTokenGenerator:
    """A generator over ``key``, frozen where the support's ``NOW`` is."""
    return OidcTokenGenerator(
        algorithms,
        make_key_set(key),
        _AUDIENCE,
        issuers,
        clock=_clock(),
    )


def _claims(token: str, key: RSAKey, *, algorithms: list[str] | None = None) -> dict[str, object]:
    """Decode ``token`` against ``key``, passing ``algorithms`` when one is named."""
    return dict(jwt.decode(token, make_key_set(key), algorithms=algorithms).claims)


def _token_of(output: io.StringIO) -> str:
    """Return the token a run printed: its whole output, stripped."""
    return output.getvalue().strip()


async def test_it_mints_a_token_for_the_only_configured_firewall() -> None:
    style, output = _style()
    key = make_key()
    command = OidcTokenGenerateCommand({"main": _generator(key)}, _clock())

    code = await command(style, "alice")

    assert code == 0
    decoded = jwt.decode(_token_of(output), make_key_set(key))
    assert decoded.header == {"alg": "RS256", "typ": "at+jwt"}
    assert decoded.claims == {
        "sub": "alice",
        "iat": NOW,
        "aud": _AUDIENCE,
        "iss": _ISSUER,
    }


async def test_the_token_is_the_only_thing_it_prints() -> None:
    style, output = _style()
    key = make_key()
    command = OidcTokenGenerateCommand({"main": _generator(key)}, _clock())

    code = await command(style, "alice")

    assert code == 0
    assert len(output.getvalue().splitlines()) == 1
    assert _claims(_token_of(output), key)["sub"] == "alice"


async def test_the_firewall_named_is_the_generator_that_signs() -> None:
    main_key = make_key("main-key")
    api_key = make_key("api-key")
    command = OidcTokenGenerateCommand(
        {"main": _generator(main_key), "api": _generator(api_key)},
        _clock(),
    )

    api_style, api_output = _style()
    assert await command(api_style, "alice", firewall="api") == 0
    main_style, main_output = _style()
    assert await command(main_style, "alice", firewall="main") == 0

    assert _claims(_token_of(api_output), api_key)["sub"] == "alice"
    assert _claims(_token_of(main_output), main_key)["sub"] == "alice"
    assert _token_of(api_output) != _token_of(main_output)


async def test_an_unknown_firewall_is_refused() -> None:
    style, output = _style()
    command = OidcTokenGenerateCommand({"main": _generator(make_key())}, _clock())

    code = await command(style, "alice", firewall="missing")

    assert code == 1
    assert 'Invalid firewall. Available firewalls: "main".' in output.getvalue()


async def test_a_firewall_must_be_named_when_several_are_configured() -> None:
    style, output = _style()
    command = OidcTokenGenerateCommand(
        {"main": _generator(make_key()), "api": _generator(make_key())},
        _clock(),
    )

    code = await command(style, "alice")

    assert code == 1
    assert 'Please choose a firewall. Available firewalls: "main", "api".' in output.getvalue()


async def test_a_run_without_any_generator_configured_is_refused() -> None:
    style, output = _style()

    code = await OidcTokenGenerateCommand({}, _clock())(style, "alice")

    assert code == 1
    assert "No OIDC token generator configured." in output.getvalue()


async def test_a_ttl_lands_on_the_exp_claim() -> None:
    style, output = _style()
    key = make_key()
    command = OidcTokenGenerateCommand({"main": _generator(key)}, _clock())

    code = await command(style, "alice", ttl=3600)

    assert code == 0
    assert _claims(_token_of(output), key)["exp"] == NOW + 3600


async def test_a_negative_ttl_is_refused_with_the_generator_reason() -> None:
    style, output = _style()
    command = OidcTokenGenerateCommand({"main": _generator(make_key())}, _clock())

    code = await command(style, "alice", ttl=-1)

    assert code == 1
    assert "Time to live must be a positive integer." in output.getvalue()


async def test_a_relative_not_before_is_counted_from_the_clock() -> None:
    style, output = _style()
    key = make_key()
    command = OidcTokenGenerateCommand({"main": _generator(key)}, _clock())

    code = await command(style, "alice", not_before="-5 minutes")

    assert code == 0
    assert _claims(_token_of(output), key)["nbf"] == NOW - 300


async def test_a_forward_offset_not_before_is_counted_from_the_clock() -> None:
    style, output = _style()
    key = make_key()
    command = OidcTokenGenerateCommand({"main": _generator(key)}, _clock())

    code = await command(style, "alice", not_before="+1 hour")

    assert code == 0
    assert _claims(_token_of(output), key)["nbf"] == NOW + 3600


async def test_a_keyword_not_before_is_read_by_the_grammar() -> None:
    style, output = _style()
    key = make_key()
    command = OidcTokenGenerateCommand({"main": _generator(key)}, _clock())

    code = await command(style, "alice", not_before="tomorrow")

    assert code == 0
    # The clock is frozen at 1970-01-12 13:46:40 UTC, so tomorrow is the
    # midnight of 1970-01-13.
    assert _claims(_token_of(output), key)["nbf"] == int(
        datetime(1970, 1, 13, tzinfo=UTC).timestamp(),
    )


async def test_an_absolute_not_before_is_taken_as_given() -> None:
    style, output = _style()
    key = make_key()
    command = OidcTokenGenerateCommand({"main": _generator(key)}, _clock())

    code = await command(style, "alice", not_before="2030-01-01 00:00:00")

    assert code == 0
    assert _claims(_token_of(output), key)["nbf"] == int(
        datetime(2030, 1, 1, tzinfo=UTC).timestamp(),
    )


async def test_a_not_before_the_grammar_cannot_read_is_refused() -> None:
    style, output = _style()
    command = OidcTokenGenerateCommand({"main": _generator(make_key())}, _clock())

    code = await command(style, "alice", not_before="garbage")

    assert code == 1
    assert 'The "--not-before" option must be a valid date, "garbage" given.' in output.getvalue()


async def test_an_empty_not_before_is_refused() -> None:
    style, output = _style()
    command = OidcTokenGenerateCommand({"main": _generator(make_key())}, _clock())

    code = await command(style, "alice", not_before="")

    assert code == 1
    assert 'The "--not-before" option must be a valid date, "" given.' in output.getvalue()


async def test_the_algorithm_named_is_the_one_signed_with() -> None:
    style, output = _style()
    key = make_key()
    command = OidcTokenGenerateCommand(
        {"main": _generator(key, algorithms=("RS256", "RS512"))},
        _clock(),
    )

    code = await command(style, "alice", algorithm="RS512")

    assert code == 0
    token = _token_of(output)
    assert jwt.decode(token, make_key_set(key), algorithms=["RS512"]).header["alg"] == "RS512"


async def test_the_issuer_named_lands_on_the_iss_claim() -> None:
    style, output = _style()
    key = make_key()
    command = OidcTokenGenerateCommand(
        {"main": _generator(key, issuers=(_ISSUER, _OTHER_ISSUER))},
        _clock(),
    )

    code = await command(style, "alice", issuer=_OTHER_ISSUER)

    assert code == 0
    assert _claims(_token_of(output), key)["iss"] == _OTHER_ISSUER


async def test_a_refusal_from_the_generator_names_the_choice() -> None:
    style, output = _style()
    command = OidcTokenGenerateCommand({"main": _generator(make_key())}, _clock())

    code = await command(style, "alice", algorithm="ES256")

    assert code == 1
    assert '"ES256" is not a valid algorithm. Available algorithms: "RS256".' in output.getvalue()


async def test_every_option_together_mints_the_token_they_name() -> None:
    style, output = _style()
    key = make_key()
    command = OidcTokenGenerateCommand(
        {
            "main": _generator(make_key(), algorithms=("RS256", "RS512")),
            "api": _generator(
                key,
                algorithms=("RS256", "RS512"),
                issuers=(_ISSUER, _OTHER_ISSUER),
            ),
        },
        _clock(),
    )

    code = await command(
        style,
        "alice",
        firewall="api",
        algorithm="RS512",
        issuer=_OTHER_ISSUER,
        ttl=3600,
        not_before="+1 hour",
    )

    assert code == 0
    decoded = jwt.decode(_token_of(output), make_key_set(key), algorithms=["RS512"])
    assert decoded.header["alg"] == "RS512"
    assert decoded.claims == {
        "sub": "alice",
        "iat": NOW,
        "aud": _AUDIENCE,
        "iss": _OTHER_ISSUER,
        "exp": NOW + 3600,
        "nbf": NOW + 3600,
    }


async def test_a_command_built_without_a_clock_mints_a_token() -> None:
    style, output = _style()
    key = make_key()
    command = OidcTokenGenerateCommand({"main": _generator(key)})

    code = await command(style, "alice")

    assert code == 0
    assert _claims(_token_of(output), key)["iat"] == NOW
