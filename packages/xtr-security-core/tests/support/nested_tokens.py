"""Standing in for the codec a session keeps a token's nested tokens through.

A token hands the token it nests — a switch's original — to the encoder and the
decoder the code writing the session passes down, so its own hooks are tested
here with a codec that keeps each nested token by its place, and with one that
fails the test when a token that nests nothing asks for it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NoReturn, cast, final

if TYPE_CHECKING:
    from xtr_security_core.authentication.token.token_interface import TokenInterface

__all__ = ["NestedTokens", "nests_nothing"]


def nests_nothing(value: object) -> NoReturn:
    """Fail the test: a token that nests no other never hands one on."""
    raise AssertionError(f"Asked to keep or rebuild a nested token: {value!r}.")


@final
class NestedTokens:
    """Keeps every token it is handed by its place, and hands it back by that place."""

    __slots__ = ("kept",)

    def __init__(self) -> None:
        self.kept: list[TokenInterface] = []

    def encode(self, token: TokenInterface) -> dict[str, object]:
        """Keep ``token``, and answer the place it is kept at."""
        self.kept.append(token)
        return {"place": len(self.kept) - 1}

    def decode(self, value: object) -> TokenInterface | None:
        """Hand back the token kept at the place ``value`` names, or ``None`` for none."""
        if not isinstance(value, dict):
            return None
        place = cast("dict[str, object]", value).get("place")
        if not isinstance(place, int) or not 0 <= place < len(self.kept):
            return None
        return self.kept[place]
