"""The identifier every entity is named by, and a reading that cuts it short."""

from __future__ import annotations

from typing import Final

from typing_extensions import override

__all__ = ["EntityTrait"]

#: How much of an identifier a reading shows before cutting it off. Eight
#: characters are enough to tell two tokens apart in a log and far too few to
#: be worth anything to whoever reads that log.
_SHOWN: Final[int] = 8


class EntityTrait:
    """Holds the identifier an entity is named by.

    A mixin: an entity composes this with the traits of whatever it is — a
    token, a client, a scope — and gets the identifier accessors, and a safe
    reading, without writing either.

    The state is declared as an annotation and not as a slot, deliberately. Two
    mixins that each claim slots cannot be combined into one class, and an
    entity here composes three or four of them, so the state lives in the
    instance dictionary an entity has anyway.

    Nothing sets a default identifier. Reading one before it is set raises, the
    same way a mapped column nobody filled does, rather than handing back an
    empty string that would be written into a token as if it were a name.
    """

    _identifier: str

    def get_identifier(self) -> str:
        """Return the identifier this entity is named by."""
        return self._identifier

    def set_identifier(self, identifier: str) -> None:
        """Name this entity ``identifier``."""
        self._identifier = identifier

    @override
    def __repr__(self) -> str:
        """Name the type and a cut-short identifier, and nothing else.

        An entity holds credentials, or things close enough to count: the user
        code a device's owner types, a client's secret, the scopes a token was
        granted. None of it belongs in a log line or a traceback, and an
        identifier is only shown far enough to correlate two readings of the
        same entity.
        """
        try:
            identifier = self._identifier
        except AttributeError:
            return f"{type(self).__name__}(identifier=unset)"
        return f"{type(self).__name__}(identifier={_cut_short(identifier)!r})"


def _cut_short(identifier: str) -> str:
    """Return the start of ``identifier``, marked when there was more of it."""
    if len(identifier) <= _SHOWN:
        return identifier
    return f"{identifier[:_SHOWN]}..."
