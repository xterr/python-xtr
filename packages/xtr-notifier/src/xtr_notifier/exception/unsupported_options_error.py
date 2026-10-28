"""Message options rendered for another provider."""

from __future__ import annotations

from .logic_error import LogicError

__all__ = ["UnsupportedOptionsError"]


class UnsupportedOptionsError(LogicError):
    """A transport was handed options another provider's builder rendered.

    Attributes:
        transport: The transport that refused the options.
        supported: The kind of options it reads.
        given: What it was handed instead.
    """

    transport: str
    supported: str
    given: str

    def __init__(self, transport: str, supported: str, given: str) -> None:
        """Name the transport, the options it reads and what it was handed.

        Args:
            transport: The transport that refused the options.
            supported: The kind of options it reads.
            given: The kind of options it was handed.
        """
        self.transport = transport
        self.supported = supported
        self.given = given
        super().__init__(
            f'The "{transport}" transport only supports instances of "{supported}" '
            f'for options (instance of "{given}" given).'
        )
