"""A type expression as it is written in code, named without running the code of its classes."""

from __future__ import annotations

from types import NoneType, UnionType
from typing import Annotated, Final, Literal, cast, get_args, get_origin

from ._type_names import qualified_name_of

__all__ = ["written_name_of"]

# What a type is called when naming it raises, or goes deeper than the stack.
_UNNAMED: Final = "a type that cannot be named"

# The union the typing module builds, which ``X | Y`` builds too where ``X`` is one of its forms;
# the same class as the other on Python 3.14.
_TYPING_UNION: Final = cast("object", get_origin(Literal[0] | None))


def written_name_of(type_: object) -> str:
    """Name ``type_`` as written, or by a fixed name when naming it raises.

    A class is named by its qualified name, read past its metaclass, in most type expressions:
    the expression is taken apart rather than shown, which would ask each class in it for its
    name, and a class is told apart before anything else is read of it, which would ask its
    metaclass. Not in all: taking apart ``Callable[[X], ...]`` with a single parameter is left to
    the typing module, which reads attributes of ``X``, so a class refusing those leaves the
    whole type named "a type that cannot be named". Showing what is neither a class nor an
    expression — an annotation's metadata, a literal's values — runs their own code, which may
    raise; so may a type nested deeper than the stack.
    """
    try:
        return _written(type_)
    except Exception:  # noqa: BLE001 - whatever naming runs leaves the type unnamed, not the call failed
        return _UNNAMED


def _written(type_: object) -> str:
    """Write ``type_`` as it is written in code, its classes by their qualified names."""
    if type_ is not NoneType and isinstance(type_, type):
        return qualified_name_of(type_)
    origin = cast("object", get_origin(type_))
    arguments: tuple[object, ...] = get_args(type_)
    if origin is None:
        return _written_alone(type_)
    if origin is _TYPING_UNION or origin is UnionType:
        return " | ".join(map(_written, arguments))
    if origin is Literal:
        return f"Literal[{', '.join(map(repr, arguments))}]"
    if origin is Annotated:
        metadata = ", ".join(map(repr, arguments[1:]))
        return f"Annotated[{_written(arguments[0])}, {metadata}]"
    return f"{_written(origin)}[{', '.join(map(_written, arguments))}]"


def _written_alone(type_: object) -> str:
    """Write what takes no arguments, a class aside: ``None``, ``...``, a callable's parameters."""
    if type_ is NoneType or type_ is None:
        return "None"
    if type_ is Ellipsis:
        return "..."
    if isinstance(type_, list):
        return f"[{', '.join(map(_written, cast('list[object]', type_)))}]"
    return repr(type_)
