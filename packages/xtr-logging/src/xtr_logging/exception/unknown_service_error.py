"""Configuration names a service that was not supplied."""

from __future__ import annotations

from .logging_error import LoggingError

__all__ = ["UnknownServiceError"]


class UnknownServiceError(LoggingError):
    """Configuration names a service that was not supplied.

    A service is an object handed to the factory by id: a handler, formatter,
    processor or activation strategy.
    """

    kind: str
    service_id: str
    known: tuple[str, ...]

    def __init__(self, kind: str, service_id: str, known: tuple[str, ...]) -> None:
        """Record what kind of service, its id, and the ids supplied for that kind."""
        self.kind = kind
        self.service_id = service_id
        self.known = known
        supplied = ", ".join(known) or "<none>"
        super().__init__(f"no {kind} service {service_id!r} was supplied; supplied: {supplied}")
