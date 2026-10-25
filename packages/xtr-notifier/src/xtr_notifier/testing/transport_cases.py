"""What a provider transport must do, as data a test hands to the checks."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import final

from xtr_notifier.message import MessageInterface
from xtr_notifier.transport import AbstractTransport, TransportInterface

__all__ = ["TransportCases"]


@final
@dataclass(frozen=True, slots=True)
class TransportCases:
    """The cases :func:`~xtr_notifier.testing.assert_transport_cases` drives a transport over.

    Every provider transport owes the same things — a string form without
    credentials, the messages it sends, a refusal of the rest, a host and port
    that can be overridden — so a provider's test states its cases here and
    the checks are written once. The sequences are copied into tuples, so the
    cases cannot change half way through a run.

    Attributes:
        create_transport: Builds a fresh transport for each check — usually over
            a ``MockHttpClient``, since only the unsupported messages are sent,
            and those must be refused before any request.
        to_string: Pairs of the string a transport must read as, and that
            transport — one per DSN option that changes it.
        supported: Messages the transport must say it sends.
        unsupported: Messages it must refuse, both in ``supports`` and by raising
            :class:`~xtr_notifier.exception.UnsupportedMessageTypeError` when sent.
    """

    create_transport: Callable[[], AbstractTransport]
    to_string: Sequence[tuple[str, TransportInterface]] = field(
        default_factory=tuple[tuple[str, TransportInterface], ...]
    )
    supported: Sequence[MessageInterface] = field(default_factory=tuple[MessageInterface, ...])
    unsupported: Sequence[MessageInterface] = field(default_factory=tuple[MessageInterface, ...])

    def __post_init__(self) -> None:
        """Freeze the sequences, so the caller's lists cannot change the cases."""
        object.__setattr__(self, "to_string", tuple(self.to_string))
        object.__setattr__(self, "supported", tuple(self.supported))
        object.__setattr__(self, "unsupported", tuple(self.unsupported))
