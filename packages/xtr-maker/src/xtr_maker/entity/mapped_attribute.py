"""MappedAttribute: one ``name: Mapped[T] = call(...)`` line, wrapped as the formatter wraps it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, final

__all__ = ["MappedAttribute"]

_INDENT: Final = "    "


@final
@dataclass(frozen=True, slots=True)
class MappedAttribute:
    """A mapped attribute of an entity: a column or a relationship.

    Attributes:
        name: The attribute.
        annotation: The type inside ``Mapped[...]``, such as ``str | None``.
        call: The function building it, as the module binds it:
            ``mapped_column`` or ``relationship``.
        arguments: The call's arguments, each already written as source.
        mapped: The name ``Mapped`` is bound to in the module.
    """

    name: str
    annotation: str
    call: str
    arguments: tuple[str, ...] = ()
    mapped: str = "Mapped"

    def render(self, *, indent: int = 4, line_length: int = 88) -> str:
        """Return the statement, without its indentation, ending with a newline.

        It is written on one line when that line, ``indent`` columns in, fits
        ``line_length``; otherwise the arguments go on a line of their own,
        and when even that is too long, one per line with a trailing comma —
        what the formatter writes, so the file needs no formatting.
        """
        head = f"{self.name}: {self.mapped}[{self.annotation}] = {self.call}("
        joined = ", ".join(self.arguments)
        if indent + len(head) + len(joined) + 1 <= line_length:
            return f"{head}{joined})\n"
        if indent + len(_INDENT) + len(joined) <= line_length:
            return f"{head}\n{_INDENT}{joined}\n)\n"
        lines = "".join(f"{_INDENT}{argument},\n" for argument in self.arguments)
        return f"{head}\n{lines})\n"
