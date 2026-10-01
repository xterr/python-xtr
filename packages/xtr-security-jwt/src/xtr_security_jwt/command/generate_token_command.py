"""``jwt:generate-token``: mint a token for a user loaded through a provider."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, final

# The command signature is read at runtime by the console, so the injected
# parameter types stay importable here rather than under TYPE_CHECKING.
from xtr_console import Argument, ConsoleStyle, ExitCode, Option, as_command, escape
from xtr_dependency_injection import Injected, ServiceLocator  # noqa: TC002 -- read at runtime
from xtr_security_core.user.user_provider_interface import (  # noqa: TC002 -- read at runtime
    UserProviderInterface,
)

from xtr_security_jwt.command._registry import JWT_COMMANDS
from xtr_security_jwt.services.jwt_token_manager_interface import (  # noqa: TC001 -- read at runtime
    JwtTokenManagerInterface,
)

if TYPE_CHECKING:
    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["GenerateTokenCommand"]


@as_command("jwt:generate-token", registry=JWT_COMMANDS)
@final
class GenerateTokenCommand:
    """Loads a user by identifier and prints a token signed for it.

    The user is loaded through one of the configured user providers: with several
    configured, ``--provider`` picks one by name; with exactly one, it is used
    without asking. The token manager signs the token, so it verifies against the
    same keys a firewall accepts.
    """

    __slots__ = ()

    async def __call__(
        self,
        io: ConsoleStyle,
        tokens: Injected[JwtTokenManagerInterface],
        providers: Injected[ServiceLocator[UserProviderInterface]],
        identifier: Annotated[
            str, Argument(help="The identifier of the user to mint a token for.")
        ],
        *,
        provider: Annotated[
            str | None,
            Option(help="The user provider to load the user through, when several are configured."),
        ] = None,
    ) -> int:
        """Load the user and print a token signed for it."""
        chosen = await self._provider(io, providers, provider)
        if chosen is None:
            return ExitCode.FAILURE
        user = await self._load(io, chosen, identifier)
        if user is None:
            return ExitCode.FAILURE
        token = await tokens.create(user)
        io.section("Token")
        io.text(escape(token))
        return ExitCode.SUCCESS

    async def _provider(
        self,
        io: ConsoleStyle,
        providers: ServiceLocator[UserProviderInterface],
        name: str | None,
    ) -> UserProviderInterface | None:
        """Choose the user provider to load through, or explain why none can be."""
        names = list(providers.provided_services())
        if not names:
            io.error("No user provider is configured to load a user from.")
            return None
        if name is not None:
            if name not in providers:
                io.error(f"No user provider is named {escape(name)}; configured: {names}.")
                return None
            return await providers.get(name)
        if len(names) > 1:
            io.error(f"Several user providers are configured; pass --provider (one of {names}).")
            return None
        return await providers.get(names[0])

    async def _load(
        self,
        io: ConsoleStyle,
        provider: UserProviderInterface,
        identifier: str,
    ) -> UserInterface | None:
        """Load the user by identifier, or explain that it could not be found."""
        from xtr_security_core.exception import AuthenticationError  # noqa: PLC0415

        try:
            return await provider.load_user_by_identifier(identifier)
        except AuthenticationError as error:
            io.error(f"Could not load a user named {escape(identifier)}: {escape(str(error))}.")
            return None
