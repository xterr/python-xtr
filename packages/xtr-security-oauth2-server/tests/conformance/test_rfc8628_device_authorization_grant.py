"""RFC 8628 — OAuth 2.0 Device Authorization Grant.

The page a person types the user code into is the application's, so the served
deployment exposes a stand-in for it.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Final

import pytest
from fastapi import FastAPI
from xtr_dependency_injection import Injected
from xtr_security_oauth2_server_core.authorization_server import AuthorizationServer
from xtr_security_oauth2_server_core.grant.device_code_grant import USER_CODE_ALPHABET
from xtr_security_oauth2_server_core.oauth2_grants import OAuth2Grants

from tests.support.served import (
    CLIENT_ID,
    CLIENT_SECRET,
    SEED_PATH,
    int_field,
    json_of,
    seed_any_grant_client,
    served_application,
    serving,
    text_field,
)

if TYPE_CHECKING:
    import httpx

pytestmark = pytest.mark.anyio

#: Who approves, as the verification page would report them.
OWNER: Final = "ada"

#: Where this deployment's stand-in for a verification page lives.
APPROVE_PATH: Final = "/approve-device"

#: The entropy section 6.1 asks a user code to carry.
REQUIRED_ENTROPY_BITS: Final = 20


def _verification(app: FastAPI) -> None:
    """Mount this deployment's stand-in for a device verification page."""

    @app.post(APPROVE_PATH)
    async def approve(
        server: Injected[AuthorizationServer],
        device_code: str,
        *,
        user_id: str = OWNER,
        approved: bool = True,
    ) -> dict[str, str]:
        await server.complete_device_authorization_request(device_code, user_id, approved)

        return {"recorded": "yes"}


def _application() -> FastAPI:
    """Return a deployment running the device flow, with a verification page."""
    return served_application(extend=_verification)


async def _device_codes(client: httpx.AsyncClient) -> tuple[str, str]:
    """Ask for the pair of codes, and return the device code and the user code."""
    await seed_any_grant_client(client)
    answered = await client.post(
        "/device-code",
        data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
    )
    assert answered.status_code == 200, answered.text
    issued = json_of(answered)

    return text_field(issued, "device_code"), text_field(issued, "user_code")


async def _poll(client: httpx.AsyncClient, device_code: str, **extra: str) -> httpx.Response:
    """Poll the token endpoint the way a device does."""
    return await client.post(
        "/token",
        data={
            "grant_type": OAuth2Grants.DEVICE_CODE,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "device_code": device_code,
            **extra,
        },
    )


# Section 3.1 — Device Authorization Request


async def test_a_device_names_itself_and_needs_nothing_else() -> None:
    # "client_id — REQUIRED ... public clients provide the "client_id"
    # parameter to identify themselves" (section 3.1): a client holding no
    # secret is answered on its identifier alone.
    async with serving(_application()) as client:
        _ = await client.post(
            SEED_PATH,
            params={"identifier": "a-device-client", "secret": "", "grant": ""},
        )
        answered = await client.post("/device-code", data={"client_id": "a-device-client"})

    assert answered.status_code == 200
    assert text_field(json_of(answered), "device_code")


async def test_a_request_naming_no_client_is_refused() -> None:
    # The same rule read the other way: the parameter is required (section
    # 3.1), so a request naming no client is refused.
    async with serving(_application()) as client:
        await seed_any_grant_client(client)
        answered = await client.post("/device-code", data={})

    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "invalid_request"


async def test_a_parameter_sent_without_a_value_counts_as_omitted() -> None:
    # "Parameters sent without a value MUST be treated as if they were omitted
    # from the request" (section 3.1): a client named empty has named none.
    async with serving(_application()) as client:
        await seed_any_grant_client(client)
        answered = await client.post("/device-code", data={"client_id": ""})

    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "invalid_request"


async def test_a_parameter_this_server_does_not_know_is_ignored() -> None:
    # "The authorization server MUST ignore unrecognized request parameters"
    # (section 3.1).
    async with serving(_application()) as client:
        await seed_any_grant_client(client)
        answered = await client.post(
            "/device-code",
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "nobody_defined_this": "whatever",
            },
        )

    assert answered.status_code == 200


async def test_a_scope_the_client_is_not_registered_for_is_refused() -> None:
    # The request carries the ``scope`` of RFC 6749 section 3.3 (section 3.1),
    # and this server judges it as it does everywhere else.
    async with serving(_application()) as client:
        await seed_any_grant_client(client)
        answered = await client.post(
            "/device-code",
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "scope": "nothing-registered",
            },
        )

    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "invalid_scope"


# Section 3.2 — Device Authorization Response


async def test_the_answer_carries_everything_the_standard_requires() -> None:
    # "device_code — REQUIRED", "user_code — REQUIRED", "verification_uri —
    # REQUIRED", "expires_in — REQUIRED" (section 3.2).
    async with serving(_application()) as client:
        await seed_any_grant_client(client)
        answered = await client.post(
            "/device-code",
            data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
        )

    issued = json_of(answered)
    assert text_field(issued, "device_code")
    assert text_field(issued, "user_code")
    assert text_field(issued, "verification_uri")
    assert int_field(issued, "expires_in") > 0


async def test_the_answer_is_two_hundred_and_json_and_uncached() -> None:
    # "includes them in the HTTP response body using the "application/json"
    # format with a 200 (OK) status code" (section 3.2), and the example answer
    # there carries ``Cache-Control: no-store``.
    async with serving(_application()) as client:
        await seed_any_grant_client(client)
        answered = await client.post(
            "/device-code",
            data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
        )

    assert answered.status_code == 200
    assert answered.headers["content-type"].startswith("application/json")
    assert answered.headers["cache-control"] == "no-store"


async def test_the_answer_may_carry_a_uri_with_the_code_already_in_it() -> None:
    # "verification_uri_complete — OPTIONAL. A verification URI that includes
    # the "user_code" ... which is designed for non-textual transmission"
    # (section 3.2).
    async with serving(_application()) as client:
        await seed_any_grant_client(client)
        answered = await client.post(
            "/device-code",
            data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
        )

    issued = json_of(answered)
    complete = text_field(issued, "verification_uri_complete")
    assert text_field(issued, "verification_uri") in complete
    assert text_field(issued, "user_code") in complete


async def test_the_answer_says_how_long_a_device_should_wait_between_polls() -> None:
    # "interval — OPTIONAL. The minimum amount of time in seconds that the
    # client SHOULD wait between polling requests to the token endpoint. If no
    # value is provided, clients MUST use 5 as the default" (section 3.2).
    async with serving(_application()) as client:
        await seed_any_grant_client(client)
        answered = await client.post(
            "/device-code",
            data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
        )

    assert int_field(json_of(answered), "interval") > 0


# Section 3.3 — User Interaction


async def test_the_person_is_sent_somewhere_to_type_the_code() -> None:
    # "Authorization servers supporting this specification MUST implement a
    # user-interaction sequence that starts with the user navigating to
    # "verification_uri" and continues with them supplying the "user_code""
    # (section 3.3). The page itself is the application's — there is no
    # endpoint for it here — so what this server owes is the address of it and
    # a code to type there.
    async with serving(_application()) as client:
        _, user_code = await _device_codes(client)

    assert user_code


# Section 3.4 — Device Access Token Request


async def test_the_flow_is_asked_for_by_the_name_the_standard_registers() -> None:
    # "grant_type — REQUIRED. Value MUST be set to
    # "urn:ietf:params:oauth:grant-type:device_code"" (section 3.4).
    assert OAuth2Grants.DEVICE_CODE == "urn:ietf:params:oauth:grant-type:device_code"
    async with serving(_application()) as client:
        device_code, _ = await _device_codes(client)
        _ = await client.post(APPROVE_PATH, params={"device_code": device_code})
        answered = await client.post(
            "/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "device_code": device_code,
            },
        )

    assert answered.status_code == 200
    assert text_field(json_of(answered), "access_token")


async def test_a_poll_naming_another_grant_type_earns_nothing() -> None:
    # The same requirement read the other way: the value MUST be the URN the
    # standard registers (section 3.4), so the short name a device might send
    # instead is a flow this server does not run and is answered
    # ``unsupported_grant_type`` (RFC 6749 section 5.2) rather than a token —
    # even with an approved device code in the same request.
    async with serving(_application()) as client:
        device_code, _ = await _device_codes(client)
        _ = await client.post(APPROVE_PATH, params={"device_code": device_code})
        answered = await client.post(
            "/token",
            data={
                "grant_type": "device_code",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "device_code": device_code,
            },
        )

    refused = json_of(answered)
    assert answered.status_code == 400
    assert text_field(refused, "error") == "unsupported_grant_type"
    assert "access_token" not in refused


async def test_a_poll_naming_no_device_code_is_refused() -> None:
    # "device_code — REQUIRED" (section 3.4): a poll that names the flow but no
    # code is refused.
    async with serving(_application()) as client:
        await seed_any_grant_client(client)
        answered = await client.post(
            "/token",
            data={
                "grant_type": OAuth2Grants.DEVICE_CODE,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
        )

    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "invalid_request"


# Section 3.5 — Device Access Token Response


async def test_a_device_nobody_has_approved_yet_is_told_to_keep_waiting() -> None:
    # "authorization_pending — The authorization request is still pending as the
    # end user hasn't yet completed the user-interaction steps" (section 3.5).
    async with serving(_application()) as client:
        device_code, _ = await _device_codes(client)
        answered = await _poll(client, device_code)

    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "authorization_pending"


async def test_a_device_polling_too_fast_is_told_to_slow_down() -> None:
    # "slow_down — A variant of "authorization_pending", the authorization
    # request is still pending and polling should continue, but the interval
    # MUST be increased by 5 seconds for this and all subsequent requests"
    # (section 3.5): a second poll inside the interval is told so.
    async with serving(_application()) as client:
        device_code, _ = await _device_codes(client)
        _ = await _poll(client, device_code)
        answered = await _poll(client, device_code)

    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "slow_down"


async def test_a_device_the_owner_refused_is_told_so() -> None:
    # "access_denied — The authorization request was denied" (section 3.5).
    async with serving(_application()) as client:
        device_code, _ = await _device_codes(client)
        _ = await client.post(
            APPROVE_PATH,
            params={"device_code": device_code, "approved": False},
        )
        answered = await _poll(client, device_code)

    assert answered.status_code != 200
    assert text_field(json_of(answered), "error") == "access_denied"


async def test_an_approved_device_is_issued_a_token() -> None:
    # "If the user has approved the grant, the token endpoint responds with a
    # success response defined in Section 5.1 of [RFC6749]" (section 3.5).
    async with serving(_application()) as client:
        device_code, _ = await _device_codes(client)
        _ = await client.post(APPROVE_PATH, params={"device_code": device_code})
        answered = await _poll(client, device_code)

    issued = json_of(answered)
    assert answered.status_code == 200
    assert text_field(issued, "token_type") == "Bearer"
    assert text_field(issued, "access_token")
    assert answered.headers["cache-control"] == "no-store"


async def test_a_device_code_already_exchanged_cannot_be_exchanged_again() -> None:
    # The code is single-use, so a second poll after the token was issued is
    # not another token; the answer is one of the errors section 3.5 defines
    # over RFC 6749 section 5.2.
    async with serving(_application()) as client:
        device_code, _ = await _device_codes(client)
        _ = await client.post(APPROVE_PATH, params={"device_code": device_code})
        first = await _poll(client, device_code)
        again = await _poll(client, device_code)

    assert first.status_code == 200
    assert again.status_code != 200
    assert "access_token" not in json_of(again)


async def test_a_device_code_this_server_never_issued_is_refused() -> None:
    # Nothing is pending for a code that was never issued, so the answer is a
    # refusal rather than ``authorization_pending`` (section 3.5).
    async with serving(_application()) as client:
        await seed_any_grant_client(client)
        answered = await _poll(client, "not-a-device-code")

    assert answered.status_code != 200
    refused = json_of(answered)
    assert text_field(refused, "error") != "authorization_pending"
    assert "access_token" not in refused


# Section 6.1 — User Code Brute Forcing


def test_the_user_code_alphabet_is_the_one_the_standard_suggests() -> None:
    # Section 6.1 discusses a user code "of 8 characters from a 20-character
    # case-insensitive alphabet", which is the example this server follows:
    # the twenty consonants, so no code reads as a word and no character can be
    # misread for another.
    assert USER_CODE_ALPHABET == "BCDFGHJKLMNPQRSTVWXZ"
    assert len(USER_CODE_ALPHABET) == 20
    assert set(USER_CODE_ALPHABET).isdisjoint(set("AEIOU01"))


async def test_the_user_code_carries_more_entropy_than_the_standard_asks_for() -> None:
    # "it is RECOMMENDED to use a user code of sufficient entropy ... at least
    # 20 bits" (section 6.1): eight characters from a twenty-character alphabet
    # is about 34.6 bits.
    async with serving(_application()) as client:
        _, user_code = await _device_codes(client)

    entropy = len(user_code) * math.log2(len(USER_CODE_ALPHABET))
    assert len(user_code) == 8
    assert entropy > REQUIRED_ENTROPY_BITS


async def test_a_user_code_is_only_ever_issued_once() -> None:
    # Section 6.1's countermeasure against guessing rests on a code being
    # usable once; two devices starting a flow are never handed the same one.
    async with serving(_application()) as client:
        _, first = await _device_codes(client)
        _, second = await _device_codes(client)

    assert first != second
