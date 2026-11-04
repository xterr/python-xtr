"""Find a header in a collection, checking it is of the class a test expects."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from xtr_mime.header import Headers

__all__ = ["header_of"]

T = TypeVar("T")


def header_of(headers: Headers, name: str, header_class: type[T]) -> T:
    header = headers.get(name)
    assert isinstance(header, header_class)
    return header
