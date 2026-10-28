"""The sweep that asks every authenticator whether it handles a request.

The pass is a self-contained sweep — it reads the wired authenticators and
one request, and reports which authenticators apply — so it lives apart from
the manager, which owns what is done with the findings: parking them on the
request's security state and handing them to the pass that authenticates.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_security_core.exception import InvalidArgumentError

from xtr_security_http.authenticator.authenticator_interface import AuthenticatorInterface

from ._manager_reporting import log_debug

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_logging_contracts import LoggerInterface

__all__ = ["run_supports_pass"]


def run_supports_pass(
    authenticators: Sequence[AuthenticatorInterface],
    request: ServerRequestInterface,
    *,
    firewall_name: str,
    logger: LoggerInterface | None,
) -> tuple[
    tuple[AuthenticatorInterface, ...],
    tuple[AuthenticatorInterface, ...],
    bool,
]:
    """Ask every authenticator whether it handles ``request``, and report the whole picture.

    Returns the authenticators that did not apply, the ones that did, and
    whether only lazy ones are among the supporters — every supporter
    answered ``None``, none of them sure a credential is presented.

    Raises:
        InvalidArgumentError: When one of the authenticators is no
            :class:`~xtr_security_http.authenticator.authenticator_interface.AuthenticatorInterface`
            — a wiring mistake, not a request failure.
    """
    lazy = True
    skipped: list[AuthenticatorInterface] = []
    supporters: list[AuthenticatorInterface] = []
    for authenticator in authenticators:
        # The sequence is typed, but nothing stops a caller from wiring a
        # duck-typed impostor in; the pass refuses one here, where the
        # mistake is about to cost a request.
        if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            authenticator,
            AuthenticatorInterface,
        ):
            raise InvalidArgumentError(
                f'The authenticator "{type(authenticator).__name__}" does not implement '
                f"AuthenticatorInterface.",
            )
        supported = authenticator.supports(request)
        if supported is False:
            log_debug(
                logger,
                'Authenticator "{authenticator}" does not support the request.',
                {
                    "firewall": firewall_name,
                    "authenticator": type(authenticator).__name__,
                },
            )
            skipped.append(authenticator)
        else:
            log_debug(
                logger,
                'Authenticator "{authenticator}" supports the request.',
                {
                    "firewall": firewall_name,
                    "authenticator": type(authenticator).__name__,
                },
            )
            supporters.append(authenticator)
            lazy = supported is None and lazy
    if supporters:
        log_debug(
            logger,
            'Authenticators "{authenticators}" support the request.',
            {
                "firewall": firewall_name,
                "authenticators": [type(authenticator).__name__ for authenticator in supporters],
            },
        )
    return tuple(skipped), tuple(supporters), lazy
