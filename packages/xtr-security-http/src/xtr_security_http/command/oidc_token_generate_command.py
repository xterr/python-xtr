"""``security:oidc:generate-token``: mint an OIDC access token for a user."""

from __future__ import annotations

from collections.abc import (
    Mapping,  # noqa: TC003 -- the container reads the constructor's annotations at runtime
)
from typing import TYPE_CHECKING, Annotated, final

# SystemClock is read at runtime, so the clock's interface rides the same
# import: the container reads the constructor's annotations at runtime too.
from xtr_clock import ClockInterface, SystemClock
from xtr_clock.exception import InvalidModifierError
from xtr_console import Argument, ConsoleStyle, ExitCode, Option, as_command, escape
from xtr_security_core.exception import InvalidArgumentError

# The generator names what the registry holds; the container reads that
# annotation at runtime, so it cannot hide under TYPE_CHECKING.
from xtr_security_http.access_token.oidc import (  # noqa: TC001 -- read at runtime
    OidcTokenGenerator,
)
from xtr_security_http.command._registry import SECURITY_HTTP_COMMANDS

if TYPE_CHECKING:
    from datetime import datetime

__all__ = ["OidcTokenGenerateCommand"]


@as_command("security:oidc:generate-token", registry=SECURITY_HTTP_COMMANDS)
@final
class OidcTokenGenerateCommand:
    """Mints the access token a firewall's generator signs, and prints it.

    The generators arrive one per firewall — the registry the security bundle
    fills as it wires the firewalls — so a token is minted by the firewall
    named, or by the only one configured. Everything the token carries beyond
    the user it names is either named on the command line or declared as the
    only one, so a token never leaves here carrying a value nobody chose.
    """

    __slots__ = ("_clock", "_generators")

    def __init__(
        self,
        generators: Mapping[str, OidcTokenGenerator],
        clock: ClockInterface | None = None,
    ) -> None:
        """Record the per-firewall generators and the clock a not-before counts from.

        Args:
            generators: The token generator of each firewall configured to
                mint its own tokens, keyed by the firewall's name.
            clock: What a relative not-before — ``"-5 minutes"`` — is counted
                from.
        """
        self._generators = generators
        self._clock = clock if clock is not None else SystemClock()

    async def __call__(  # noqa: PLR0913 -- the user identifier and the five knobs a minted token carries
        self,
        io: ConsoleStyle,
        user_identifier: Annotated[
            str,
            Argument(
                name="user-identifier",
                help="The identifier of the user to mint a token for.",
            ),
        ],
        *,
        firewall: Annotated[
            str | None,
            Option(help="The firewall whose generator signs, when several are configured."),
        ] = None,
        algorithm: Annotated[
            str | None,
            Option(help="The algorithm to sign with, when several are declared."),
        ] = None,
        issuer: Annotated[
            str | None,
            Option(help="The issuer the token names (the iss claim), when several are declared."),
        ] = None,
        ttl: Annotated[
            int | None,
            Option(help="How many seconds the token lives (the exp claim)."),
        ] = None,
        not_before: Annotated[
            str | None,
            Option(
                help="The moment the token starts being valid (the nbf claim): "
                "a date, or an offset like '-5 minutes'.",
            ),
        ] = None,
    ) -> int:
        """Generate an OIDC token for a given user, and print it."""
        try:
            generator = self._generator(firewall)
            token = generator.generate(
                user_identifier,
                algorithm,
                issuer,
                ttl,
                self._not_before(not_before),
            )
        except InvalidArgumentError as error:
            io.error(escape(str(error)))
            return ExitCode.FAILURE
        io.text(escape(token))
        return ExitCode.SUCCESS

    def _generator(self, firewall: str | None) -> OidcTokenGenerator:
        """Return the generator of the firewall named, or of the only one.

        Raises:
            InvalidArgumentError: When no generator is configured; when the
                firewall named has none; or when none is named while several
                are configured.
        """
        if not self._generators:
            raise InvalidArgumentError("No OIDC token generator configured.")
        if firewall is not None:
            if firewall not in self._generators:
                raise InvalidArgumentError(
                    f'Invalid firewall. Available firewalls: "{_joined(self._generators)}".',
                )
            return self._generators[firewall]
        if len(self._generators) != 1:
            raise InvalidArgumentError(
                f'Please choose a firewall. Available firewalls: "{_joined(self._generators)}".',
            )
        return next(iter(self._generators.values()))

    def _not_before(self, not_before: str | None) -> datetime | None:
        """Return the moment the option names, or ``None`` when it names none.

        Raises:
            InvalidArgumentError: When the option names no date the clock's
                grammar can read.
        """
        if not_before is None:
            return None
        try:
            return self._clock.now().modify(not_before)
        except InvalidModifierError as error:
            raise InvalidArgumentError(
                f'The "--not-before" option must be a valid date, "{not_before}" given.',
            ) from error


def _joined(generators: Mapping[str, OidcTokenGenerator]) -> str:
    """Join the firewalls the way a refusal lists them: quoted, comma-separated."""
    return '", "'.join(generators)
