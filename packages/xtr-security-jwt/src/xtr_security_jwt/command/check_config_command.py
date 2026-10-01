"""``jwt:check-config``: prove the configured keys can sign and verify."""

from __future__ import annotations

from typing import final

from xtr_console import ConsoleStyle, ExitCode, as_command, escape

# The console reads the command signature at runtime to inject the encoder.
from xtr_dependency_injection import Injected  # noqa: TC002

from xtr_security_jwt.command._registry import JWT_COMMANDS
from xtr_security_jwt.encoder.jwt_encoder_interface import (  # noqa: TC001 -- read at runtime
    JwtEncoderInterface,
)
from xtr_security_jwt.exception.jwt_failure_error import JwtFailureError

__all__ = ["CheckConfigCommand"]


@as_command("jwt:check-config", registry=JWT_COMMANDS)
@final
class CheckConfigCommand:
    """Signs a probe token and reads it back, proving the keys work.

    A deployment runs this after configuring its keys to learn — before a single
    request — that the signing key signs and the verifying key verifies. A
    failure names what went wrong.
    """

    __slots__ = ()

    async def __call__(self, io: ConsoleStyle, encoder: Injected[JwtEncoderInterface]) -> int:
        """Round-trip a probe token through the encoder and report the outcome."""
        try:
            token = encoder.encode({"sub": "jwt:check-config"})
            claims = encoder.decode(token)
        except JwtFailureError as error:
            io.error(f"The JWT configuration is not usable: {escape(str(error).rstrip('.'))}.")
            return ExitCode.FAILURE
        if claims.get("sub") != "jwt:check-config":
            io.error("The probe token did not round-trip its subject claim.")
            return ExitCode.FAILURE
        io.success("The JWT configuration signs and verifies.")
        return ExitCode.SUCCESS
