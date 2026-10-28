"""The endpoint a resource server reads this server's verifying keys from."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast

import pytest
from xtr_http_kernel.bridge import Response
from xtr_security_jwt.services.key_loader import RawKeyLoader

from tests.support.messages import document_of, server_request
from tests.support.signing import ALGORITHM, KEY_LOADER
from xtr_security_oauth2_server.controller.jwks_controller import JwksController
from xtr_security_oauth2_server.exception import InvalidConfigurationError

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio

_OK: Final = 200


def _controller() -> JwksController:
    """Return the endpoint over the key the suite signs with."""
    return JwksController(KEY_LOADER, ALGORITHM)


async def test_it_publishes_the_key_set_as_a_key_set_document() -> None:
    answered = await _controller().index_action(
        server_request("GET", "/.well-known/jwks.json"),
        Response(200),
    )

    assert answered.get_status_code() == _OK
    assert answered.get_header_line("content-type") == "application/jwk-set+json"


async def test_every_published_key_carries_the_id_a_token_names_it_by() -> None:
    # What lets a key be rotated without a flag day: the id is read off the key
    # material, so the published set cannot drift from what is signing.
    answered = await _controller().index_action(
        server_request("GET", "/.well-known/jwks.json"),
        Response(200),
    )

    published = await document_of(answered)
    assert isinstance(published, dict)
    keys = cast("object", published["keys"])
    assert isinstance(keys, list)
    assert keys
    for key in keys:  # pyright: ignore[reportUnknownVariableType] -- a decoded document
        assert isinstance(key, dict)
        assert key["kid"]
        # Only public halves are ever written.
        assert "d" not in key


def test_it_names_the_algorithm_and_never_the_keys() -> None:
    assert repr(_controller()) == f"JwksController(signature_algorithm={ALGORITHM!r})"


async def test_a_key_file_gone_since_start_is_reported_in_this_servers_terms(
    tmp_path: Path,
) -> None:
    missing = str(tmp_path / "oauth2.pem")
    controller = JwksController(RawKeyLoader(missing, None), ALGORITHM)

    with pytest.raises(InvalidConfigurationError) as refused:
        _ = await controller.index_action(
            server_request("GET", "/.well-known/jwks.json"),
            Response(200),
        )

    message = str(refused.value)
    assert missing in message
    assert "authorization_server.private_key" in message
    assert "oauth2-server:generate-keypair" in message
    assert "jwt" not in message.lower()
