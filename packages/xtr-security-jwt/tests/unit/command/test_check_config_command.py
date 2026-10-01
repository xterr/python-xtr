"""``jwt:check-config`` proves the keys sign and verify, or names the fault."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import pytest
from typing_extensions import override
from xtr_clock import MockClock
from xtr_console import ConsoleStyle

from tests.support.keys import RSA_PRIVATE_PEM

if TYPE_CHECKING:
    from collections.abc import Mapping
from xtr_security_jwt.command.check_config_command import CheckConfigCommand
from xtr_security_jwt.encoder.default_jwt_encoder import DefaultJwtEncoder
from xtr_security_jwt.encoder.jwt_encoder_interface import JwtEncoderInterface
from xtr_security_jwt.exception.jwt_encode_failure_error import JwtEncodeFailureError
from xtr_security_jwt.services.jws_provider.joserfc_jws_provider import JoserfcJwsProvider
from xtr_security_jwt.services.key_loader.raw_key_loader import RawKeyLoader

pytestmark = pytest.mark.anyio


def _style() -> tuple[ConsoleStyle, io.StringIO]:
    output = io.StringIO()
    style = ConsoleStyle(output, io.StringIO(), width=200, decorated=False, interactive=False)
    return style, output


def _encoder() -> DefaultJwtEncoder:
    provider = JoserfcJwsProvider(
        RawKeyLoader(RSA_PRIVATE_PEM, None),
        "RS256",
        3600,
        0,
        MockClock("2024-01-01 00:00:00"),
    )
    return DefaultJwtEncoder(provider)


async def test_it_reports_a_working_configuration() -> None:
    style, output = _style()

    code = await CheckConfigCommand()(style, _encoder())

    assert code == 0
    assert "signs and verifies" in output.getvalue()


async def test_it_reports_a_failure() -> None:
    style, output = _style()

    class Broken(JwtEncoderInterface):
        @override
        def encode(self, data: Mapping[str, object]) -> str:
            del data
            raise JwtEncodeFailureError(JwtEncodeFailureError.INVALID_CONFIG, "no key")

        @override
        def decode(self, token: str) -> Mapping[str, object]:
            del token
            return {}

    code = await CheckConfigCommand()(style, Broken())

    assert code == 1
    assert "not usable" in output.getvalue()
