"""The request a webhook is built into, before anything sends it."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import final

__all__ = ["OutgoingRequest"]


@final
@dataclass(slots=True)
class OutgoingRequest:
    """What the configurators write a webhook into, one after another.

    Mutable where almost everything else here is frozen, because building a
    webhook is a sequence: one configurator writes the headers that identify the
    event, the next writes the body, and the signer reads both back to sign what
    the earlier two produced. Each hands the same request on.

    It is a plain pair of values rather than a client's request type, so the whole
    sending side can be written, and tested, without an HTTP client installed —
    the transport turns one of these into whatever it sends.

    Attributes:
        headers: The headers to send, by name. A configurator writes the ones it
            owns and leaves the rest, so the order the chain runs in decides only
            what can be read back, never what survives.
        body: The exact bytes to send. ``None`` until a configurator sets them;
            bytes rather than text because a signature covers what goes out, and
            re-encoding text can change it.
    """

    headers: dict[str, str] = field(default_factory=dict)
    body: bytes | None = None
