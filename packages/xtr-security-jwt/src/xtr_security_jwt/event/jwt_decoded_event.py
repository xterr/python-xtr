"""The event carrying a verified token's payload, which a listener may reject."""

from __future__ import annotations

from typing import final

from xtr_event_dispatcher_contracts import Event

__all__ = ["JwtDecodedEvent"]


@final
class JwtDecodedEvent(Event):
    """Announces a verified token's payload, so a listener may inspect or reject it.

    Dispatched by the token manager once a token verifies, with its claims. A
    listener may edit the payload, or call :meth:`mark_as_invalid` to reject the
    token — which also stops the remaining listeners — so a deployment can refuse
    a token on a rule beyond the signature, such as a claim it no longer trusts.
    """

    __slots__ = ("_is_valid", "_payload")

    def __init__(self, payload: dict[str, object]) -> None:
        """Record the verified token's ``payload``, valid until a listener says otherwise."""
        self._payload = payload
        self._is_valid = True

    def get_payload(self) -> dict[str, object]:
        """Return the verified token's claims, open to change."""
        return self._payload

    def set_payload(self, payload: dict[str, object]) -> None:
        """Replace the verified token's claims."""
        self._payload = payload

    def mark_as_invalid(self) -> None:
        """Reject the token and stop the remaining listeners."""
        self._is_valid = False
        self.stop_propagation()

    def is_valid(self) -> bool:
        """Tell whether the token is still to be trusted."""
        return self._is_valid
