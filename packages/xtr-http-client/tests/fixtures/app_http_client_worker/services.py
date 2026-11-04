"""What the handler writes down."""

from __future__ import annotations

from typing import final

from xtr_dependency_injection import as_service


@final
@as_service
class Pings:
    """The number of every ping handled, in order."""

    def __init__(self) -> None:
        self.numbers: list[int] = []
