"""The lines the authentication manager's passes write, and the names in them.

The manager and the passes it runs log through the same guard — a logger
that may be absent — and name the same thing in every record: the
authenticator a line is about, not the traceable wrapper the wiring runs.
Both live here so every pass writes its records the same way.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_security_http.authenticator.debug.traceable_authenticator import TraceableAuthenticator

if TYPE_CHECKING:
    from xtr_logging_contracts import LoggerInterface
    from xtr_logging_contracts.context import Context

    from xtr_security_http.authenticator.authenticator_interface import AuthenticatorInterface

__all__ = [
    "authenticator_name",
    "log_debug",
    "log_info",
]


def authenticator_name(authenticator: AuthenticatorInterface) -> str:
    """Return the class name a log or a record should name.

    A traceable wrapper is what the wiring runs, but its name explains
    nothing; the wrapped one is what a reader is looking for.
    """
    if isinstance(authenticator, TraceableAuthenticator):
        return type(authenticator.get_authenticator()).__name__
    return type(authenticator).__name__


def log_debug(logger: LoggerInterface | None, message: str, context: Context) -> None:
    """Write ``message`` at debug level, when a logger was given."""
    if logger is not None:
        logger.debug(message, context)


def log_info(logger: LoggerInterface | None, message: str, context: Context) -> None:
    """Write ``message`` at info level, when a logger was given."""
    if logger is not None:
        logger.info(message, context)
