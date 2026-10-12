"""Events received from another system, handed to the consumer registered under their name.

An event from elsewhere — a delivery report, a payment notice, a message from a provider — is
one value type here: the name of where it came from, an id, and the payload as it arrived. A
consumer is registered under that name, and the event reaches it directly or through a message
bus.
"""

from __future__ import annotations

__all__: list[str] = []
