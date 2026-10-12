"""``oauth2-server:clear-expired-tokens``: sweep what this server issued and outlived."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, final

from xtr_console import ConsoleStyle, ExitCode, Option, as_command

from xtr_security_oauth2_server.manager.access_token_manager_interface import (  # noqa: TC001 — container hydrates this constructor at runtime
    AccessTokenManagerInterface,
)
from xtr_security_oauth2_server.manager.authorization_code_manager_interface import (  # noqa: TC001 — container hydrates this constructor at runtime
    AuthorizationCodeManagerInterface,
)
from xtr_security_oauth2_server.manager.device_code_manager_interface import (  # noqa: TC001 — container hydrates this constructor at runtime
    DeviceCodeManagerInterface,
)
from xtr_security_oauth2_server.manager.refresh_token_manager_interface import (  # noqa: TC001 — container hydrates this constructor at runtime
    RefreshTokenManagerInterface,
)

from ._registry import OAUTH2_SERVER_COMMANDS

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

__all__ = ["ClearExpiredTokensCommand"]


@as_command("oauth2-server:clear-expired-tokens", registry=OAUTH2_SERVER_COMMANDS)
@final
class ClearExpiredTokensCommand:
    """Forgets every credential this server issued whose lifetime has run out.

    Nothing is decided by this: an expired credential is already refused
    wherever it is presented, so sweeping is housekeeping — it keeps the store
    from growing without bound, and it is the reason this is the one command
    a deployment runs on a schedule rather than by hand.

    Naming no store sweeps all of them, which is what a scheduled run wants.
    The device codes are left out of that sweep when the device flow is turned
    off, since there are none; naming ``--device-codes`` sweeps them anyway,
    which is how a deployment clears up after turning the flow off.
    """

    __slots__ = (
        "_access_tokens",
        "_authorization_codes",
        "_device_codes",
        "_enable_device_code_grant",
        "_refresh_tokens",
    )

    def __init__(
        self,
        access_token_manager: AccessTokenManagerInterface,
        refresh_token_manager: RefreshTokenManagerInterface,
        authorization_code_manager: AuthorizationCodeManagerInterface,
        device_code_manager: DeviceCodeManagerInterface,
        enable_device_code_grant: bool,
    ) -> None:
        """Sweep the four stores, knowing whether the device flow runs at all.

        Args:
            access_token_manager: Where the issued access tokens live.
            refresh_token_manager: Where the issued refresh tokens live.
            authorization_code_manager: Where the issued authorization codes
                live.
            device_code_manager: Where the issued device codes live.
            enable_device_code_grant: Whether this deployment runs the flow
                for a device with no browser, which is what decides whether a
                sweep naming no store sweeps device codes too.
        """
        self._access_tokens = access_token_manager
        self._refresh_tokens = refresh_token_manager
        self._authorization_codes = authorization_code_manager
        self._device_codes = device_code_manager
        self._enable_device_code_grant = enable_device_code_grant

    async def __call__(
        self,
        io: ConsoleStyle,
        *,
        access_tokens: Annotated[
            bool,
            Option(alias="-a", help="Sweep the expired access tokens."),
        ] = False,
        refresh_tokens: Annotated[
            bool,
            Option(alias="-r", help="Sweep the expired refresh tokens."),
        ] = False,
        auth_codes: Annotated[
            bool,
            Option(alias="-c", help="Sweep the expired authorization codes."),
        ] = False,
        device_codes: Annotated[
            bool,
            Option(alias="-dc", help="Sweep the expired device codes."),
        ] = False,
    ) -> int:
        """Sweep the credentials this server issued whose lifetime has run out."""
        named = (access_tokens, refresh_tokens, auth_codes, device_codes)
        # Naming no store sweeps all of them — bar the device codes of a
        # deployment running no device flow, of which there are none.
        asked = named if any(named) else (True, True, True, self._enable_device_code_grant)
        stores = (
            (self._access_tokens.clear_expired, "access token"),
            (self._refresh_tokens.clear_expired, "refresh token"),
            (self._authorization_codes.clear_expired, "auth code"),
            (self._device_codes.clear_expired, "device code"),
        )
        for wanted, (sweep, kind) in zip(asked, stores, strict=True):
            if wanted:
                await _swept(io, sweep, kind)

        return ExitCode.SUCCESS


async def _swept(io: ConsoleStyle, sweep: Callable[[], Awaitable[int]], kind: str) -> None:
    """Sweep one store and report how many credentials of ``kind`` went."""
    gone = await sweep()
    io.success(f"Cleared {gone} expired {kind}{'' if gone == 1 else 's'}.")
