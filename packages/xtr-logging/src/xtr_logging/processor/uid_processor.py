"""Stamps every record of one unit of work with a shared random id."""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override

from xtr_logging.exception.invalid_option_error import InvalidOptionError
from xtr_logging.resettable_interface import ResettableInterface

from .processor_interface import ProcessorInterface

if TYPE_CHECKING:
    from xtr_logging.log_record import LogRecord

__all__ = ["UidProcessor"]

_MIN_LENGTH: Final = 1
_MAX_LENGTH: Final = 32


@final
class UidProcessor(ProcessorInterface, ResettableInterface):
    """Adds ``extra["uid"]`` — one id tying together the records of a request.

    Every record made between one :meth:`reset` and the next carries the same
    id, so a request's log lines can be found together even where several are
    handled at once. :meth:`reset` mints a fresh id for the next unit of work.
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
        return self._uid

    @override
    def __call__(self, record: LogRecord, /) -> LogRecord:
        """Return ``record`` with the current id in ``extra``."""
        return record.with_extra({"uid": self._uid})

    @override
    def reset(self) -> None:
        """Mint a fresh id for the next unit of work."""
        self._uid = _generate(self._length)


def _generate(length: int) -> str:
    return secrets.token_hex((length + 1) // 2)[:length]
