"""A key of the data hashed as another, whose comparison raises, as code the data carries may."""

from __future__ import annotations

from typing import final

from typing_extensions import override

__all__ = ["CollidingKey"]


@final
class CollidingKey:
    """Hashed as ``twin``: a dict looking ``twin`` up compares the two.

    The comparison raises ``words`` once the key is armed, after the dict holding it is made, as
    making it compares the keys hashed alike too.
    """

    __slots__ = ("_twin", "_words", "armed")

    def __init__(self, twin: str, words: str) -> None:
        self._twin = twin
        self._words = words
        self.armed = False

    @override
    def __hash__(self) -> int:
        return hash(self._twin)

    @override
    def __eq__(self, other: object) -> bool:
        if self.armed:
            raise RuntimeError(self._words)
        return self is other
