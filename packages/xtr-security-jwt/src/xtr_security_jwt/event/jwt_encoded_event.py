"""The event carrying a token once it has been signed."""

from __future__ import annotations

from typing import final

from xtr_event_dispatcher_contracts import Event

__all__ = ["JwtEncodedEvent"]


@final
class JwtEncodedEvent(Event):
    """Announces a token that has just been signed, for a listener to read.

    Dispatched by the token manager with the finished compact token. A read-only
    hook: the token is signed and cannot be reshaped here.
    """

    __slots__ = ("_jwt_string",)

    def __init__(self, jwt_string: str) -> None:
        """Record the signed ``jwt_string``."""
        self._jwt_string = jwt_string

    def get_jwt_string(self) -> str:
        """Return the signed compact token."""
        return self._jwt_string
