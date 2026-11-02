"""The error every other error of this package derives from."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, TypeVar

from typing_extensions import override

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["SerializerError"]

_ErrorT = TypeVar("_ErrorT", bound="SerializerError")


def _restore_error(error_type: type[_ErrorT]) -> _ErrorT:
    """Make an error of ``error_type`` without calling its constructor.

    Pickle and copy call this to allocate the instance, then restore its state onto
    it. It lives at module level so that pickle can name it.
    """
    return error_type.__new__(error_type)


class SerializerError(Exception):
    """Something the serializer could not do — catch this to catch them all.

    Serialization happens at the edges of an application: a request body read
    in, a message written to a queue. One ``except`` there has to answer for
    anything that went wrong, and this is that one; a subclass tells one cause
    from another — data that does not fit its type, a format nothing reads, a
    class hierarchy registered wrongly.

    No error of this package repeats a value it was handed. What goes through a
    serializer is often what an application must keep out of its logs — a
    password, a token, a customer's address — so a message says where the
    problem is and which types were involved, never what the value was.

    That holds only while callers keep the value out of the chain: an error
    raised *from* an exception that carries the value puts that value into the
    traceback, which is rendered whatever the message says. Raise these errors
    without chaining the input-bearing exception — catch it and raise the error
    with its typed fields, and no ``from`` clause.
    """

    @override
    def __reduce__(
        self,
    ) -> tuple[Callable[[type[Self]], Self], tuple[type[Self]], dict[str, object]]:
        """Rebuild the error from its state, without calling its constructor again.

        ``BaseException`` rebuilds an error by calling ``cls(*args)``. For an error
        whose constructor takes typed fields, that hands its composed message to the
        constructor as if it were the first field: the message nests inside itself
        on every round trip, and an error that takes several fields cannot be
        rebuilt at all. Restoring the instance state and ``args`` keeps the class,
        the fields and the message exactly as they were.
        """
        return (_restore_error, (type(self),), {**vars(self), "args": self.args})
