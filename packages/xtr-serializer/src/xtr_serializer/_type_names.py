"""A class's names as the interpreter keeps them, read without running its metaclass.

A class of the data's or the application's may have a metaclass computing ``__name__`` or
``__qualname__``; naming the class in an error must not run that code, which could raise or quote
the data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast

if TYPE_CHECKING:
    from types import GetSetDescriptorType

__all__ = ["name_of", "qualified_name_of"]

_NAME: Final = cast("GetSetDescriptorType", vars(type)["__name__"])
_QUALIFIED_NAME: Final = cast("GetSetDescriptorType", vars(type)["__qualname__"])


def name_of(kind: type) -> str:
    """Give the name ``kind`` was defined under."""
    return cast("str", _NAME.__get__(kind))


def qualified_name_of(kind: type) -> str:
    """Give the name ``kind`` was defined under, led by the classes and functions holding it."""
    return cast("str", _QUALIFIED_NAME.__get__(kind))
