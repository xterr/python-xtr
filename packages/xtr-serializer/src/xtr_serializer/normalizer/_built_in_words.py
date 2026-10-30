"""A value error's message: the application's own words, or fixed ones for a built-in type."""

from __future__ import annotations

import sys
from ipaddress import (
    IPv4Address,
    IPv4Interface,
    IPv4Network,
    IPv6Address,
    IPv6Interface,
    IPv6Network,
)
from typing import TYPE_CHECKING, Final, cast

if TYPE_CHECKING:
    from collections.abc import Mapping
    from types import CodeType

    from pydantic_core import ErrorDetails

__all__ = ["value_error_message"]

# What reading an address refuses with, by the code that refused it: strict, pydantic hands the
# text to the class itself, whose message quotes it.
_ADDRESSES: Final[Mapping[CodeType, str]] = {
    IPv4Address.__init__.__code__: "Input is not a valid IPv4 address",
    IPv6Address.__init__.__code__: "Input is not a valid IPv6 address",
    IPv4Network.__init__.__code__: "Input is not a valid IPv4 network",
    IPv6Network.__init__.__code__: "Input is not a valid IPv6 network",
    IPv4Interface.__init__.__code__: "Input is not a valid IPv4 interface",
    IPv6Interface.__init__.__code__: "Input is not a valid IPv6 interface",
}

# How pydantic refuses an email address: its reason, from email-validator, quotes the address.
_EMAIL: Final = "value is not a valid email address"

# What any other code that is not the application's raised, whose message may quote the input.
_NOT_VALID: Final = "Value error, the input is not valid for its type"

# The packages whose code reads the built-in types, beside the standard library's modules.
_BUILT_IN: Final = frozenset(
    {*sys.stdlib_module_names, "pydantic", "pydantic_core", "email_validator"}
)


def value_error_message(detail: ErrorDetails) -> str:
    """Give the message of a ``value_error``, without the input unless the application wrote it.

    pydantic reports alike a ``ValueError`` an application's validator raised and one raised by
    the code reading a built-in type — the standard library's addresses, email-validator's
    addresses —, whose message quotes the input. The error itself tells them apart: the
    outermost frame it was raised through is the function pydantic called, and only one in the
    application's own module is the application's. Its words are passed on, as a validator
    worded them; any other is replaced by fixed words for its type. The frame is only read,
    never run.

    An error carrying no exception was raised by a validator as pydantic's own custom error,
    worded as it chose — but for pydantic's email error, whose reason quotes the address.
    """
    context = cast("Mapping[str, object]", detail.get("ctx", {}))
    error = context.get("error")
    if not isinstance(error, BaseException):
        return _EMAIL if detail["msg"].startswith(f"{_EMAIL}: ") else detail["msg"]
    trace = error.__traceback__
    if trace is None:  # raised by built-in code alone, which no frame of Python ran
        return _NOT_VALID
    frame = trace.tb_frame
    if (address := _ADDRESSES.get(frame.f_code)) is not None:
        return address
    module = cast("object", frame.f_globals.get("__name__"))
    if not isinstance(module, str) or module.partition(".")[0] in _BUILT_IN:
        return _NOT_VALID
    return detail["msg"]
