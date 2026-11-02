"""Reading the options of an ``smtp://`` DSN, each refused by its name when its value is not valid.

A refusal names the option and what it must hold, and quotes the value only when it is one plain
word (see :func:`~xtr_mailer._error_text.option_value`): never the DSN, never its credentials.
"""

from __future__ import annotations

import math
import re
from typing import TYPE_CHECKING, Final

from xtr_mailer._error_text import option_value
from xtr_mailer.exception import InvalidArgumentError

if TYPE_CHECKING:
    from xtr_mailer.transport.dsn import Dsn

__all__ = ["read_count", "read_flag", "read_number", "read_text", "refusal"]

# A decimal number as a DSN writes one: no ``nan``, ``inf``, underscores or hex, which ``float``
# would read but no one means as seconds.
_NUMBER: Final = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
# Digits enough for any count of emails, few enough for ``int`` to read at once.
_COUNT: Final = re.compile(r"[0-9]{1,18}")


def refusal(key: str, requirement: str, value: str | None) -> InvalidArgumentError:
    """Return the error refusing option ``key``, which must be ``requirement``.

    ``value`` is quoted when it is one plain word, and left out otherwise or when ``None``.
    """
    shown = None if value is None else option_value(value)
    given = "" if shown is None else f', "{shown}" given'
    return InvalidArgumentError(
        f'The "{key}" option is not valid: it must be {requirement}{given}.'
    )


def read_text(dsn: Dsn, key: str, requirement: str) -> str | None:
    """Return option ``key``, or ``None`` when unset.

    Raises:
        InvalidArgumentError: The option is a list or a mapping (``key[]=``, ``key[name]=``).
    """
    match dsn.get_option(key):
        case str() | None as value:
            return value
        case _:
            raise refusal(key, requirement, None)


def read_number(dsn: Dsn, key: str, requirement: str, *, positive: bool = False) -> float | None:
    """Return option ``key`` as a finite decimal number, zero or more, or ``None`` when unset.

    Args:
        dsn: The DSN to read.
        key: The option.
        requirement: What the option must be, as its refusal says it.
        positive: Refuse zero too.

    Raises:
        InvalidArgumentError: The option is no such number.
    """
    value = read_text(dsn, key, requirement)
    if value is None:
        return None
    number = float(value) if _NUMBER.fullmatch(value.strip()) else math.nan
    if not (math.isfinite(number) and (number > 0 if positive else number >= 0)):
        raise refusal(key, requirement, value)
    return number


def read_count(dsn: Dsn, key: str, requirement: str) -> int | None:
    """Return option ``key`` as a whole number, zero or more, or ``None`` when unset.

    Raises:
        InvalidArgumentError: The option is no such number.
    """
    value = read_text(dsn, key, requirement)
    if value is None:
        return None
    if _COUNT.fullmatch(value.strip()) is None:
        raise refusal(key, requirement, value)
    return int(value)


def read_flag(dsn: Dsn, key: str) -> bool:
    """Return option ``key`` read as a boolean that is on when unset or empty.

    Raises:
        InvalidArgumentError: The option is not a boolean.
    """
    return dsn.get_option(key, "") == "" or dsn.get_boolean_option(key)
