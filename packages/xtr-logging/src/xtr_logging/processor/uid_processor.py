"""Stamps every record of one unit of work with a shared random id."""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_service_contracts import ResetInterface

from xtr_logging.exception.invalid_option_error import InvalidOptionError
from xtr_logging.log_unit import unit_state

from .processor_interface import ProcessorInterface

if TYPE_CHECKING:
    from xtr_logging.log_record import LogRecord

__all__ = ["UidProcessor"]

_MIN_LENGTH: Final = 1
_MAX_LENGTH: Final = 32


@final
class _UidBox:
    """A mutable holder for a unit's id, so it is reset in place, not replaced."""

    __slots__ = ("value",)

    def __init__(self, value: str) -> None:
        self.value = value


@final
class UidProcessor(ProcessorInterface, ResetInterface):
    """Adds ``extra["uid"]`` — one id tying together the records of a request.

    Inside a unit of work the id lives on the unit, so concurrent requests each
    get their own stable id from the one shared processor. Outside a unit the id
    lives on the instance, as before. Either way every record carries the same
    id until :meth:`reset` mints a fresh one for the next unit of work.
    """

    __slots__ = ("_length", "_uid")

    def __init__(self, length: int = 7) -> None:
        """Generate ids of ``length`` hexadecimal characters.

        Raises:
            InvalidOptionError: If ``length`` is not between 1 and 32.
        """
        if not _MIN_LENGTH <= length <= _MAX_LENGTH:
            raise InvalidOptionError(
                "length", str(length), f"must be between {_MIN_LENGTH} and {_MAX_LENGTH}"
            )
        self._length: int = length
        self._uid: str = _generate(length)

    @property
    def uid(self) -> str:
        """The id every record carries until the next :meth:`reset`."""
        box = self._box()
        return box.value if box is not None else self._uid

    @override
    def __call__(self, record: LogRecord, /) -> LogRecord:
        """Return ``record`` with the current id in ``extra``."""
        return record.with_extra({"uid": self.uid})

    @override
    def reset(self) -> None:
        """Mint a fresh id for the next unit of work.

        Inside a unit the id is replaced on the unit's holder in place, so the
        change follows the unit's context even into a synchronous callee anyio
        runs in a copied context.
        """
        box = self._box()
        if box is not None:
            box.value = _generate(self._length)
        else:
            self._uid = _generate(self._length)

    def _box(self) -> _UidBox | None:
        return unit_state(self, lambda: _UidBox(_generate(self._length)))


def _generate(length: int) -> str:
    return secrets.token_hex((length + 1) // 2)[:length]
