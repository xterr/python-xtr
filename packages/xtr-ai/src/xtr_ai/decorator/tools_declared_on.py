"""Reading ``@as_tool`` declarations back off a class."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .as_tool import TOOL_ATTRIBUTE
from .tool_declaration import ToolDeclaration

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["tools_declared_on"]


def tools_declared_on(obj: object) -> Iterable[ToolDeclaration]:
    """Return every tool declared on ``obj``'s methods, inherited ones included.

    Anything but a class declares none. A method overridden in a subclass is
    read from the subclass, so an override without the decorator is not a tool.
    """
    if not isinstance(obj, type):
        return ()
    found: dict[str, ToolDeclaration] = {}
    for klass in reversed(obj.__mro__):
        for attribute, value in vars(klass).items():
            declaration = getattr(value, TOOL_ATTRIBUTE, None)
            if isinstance(declaration, ToolDeclaration):
                found[attribute] = declaration
            else:
                _ = found.pop(attribute, None)
    return tuple(found.values())
