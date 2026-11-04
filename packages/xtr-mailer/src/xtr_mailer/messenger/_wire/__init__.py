"""A queued email and its envelope as plain data, and back — versioned, every value checked.

The data is JSON's: objects, lists, text, numbers, booleans and null, bytes as base64. Each
message, part and header carries its kind under ``$type``; only the classes listed here are
written, and only they are read back. What is read comes from a broker, so it is untrusted:
it is checked value by value, and a refusal says where and why, never what it held.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from ._addresses import read_envelope, write_envelope
from ._json import JsonObject, fields, refuse
from ._messages import read_message, write_message
from ._render_budget import check_render_cost

if TYPE_CHECKING:
    from xtr_mime import RawMessage

    from xtr_mailer.envelope import Envelope

__all__ = ["JsonObject", "read", "write"]

_VERSION: Final = 1


def write(message: RawMessage, envelope: Envelope | None) -> JsonObject:
    """Write ``message`` and ``envelope``.

    Raises:
        InvalidArgumentError: The email, or a part or header in it, is of a class the queue
            does not carry, or its parts are nested deeper than 32.
        xtr_mime.MimeError: The email cannot be read: a file attached is gone, a generator is
            left half read.
        MailerError: The envelope cannot be read from the email's headers.
    """
    return {
        "version": _VERSION,
        "message": write_message(message),
        "envelope": write_envelope(envelope),
    }


def read(data: object) -> tuple[RawMessage, Envelope | None]:
    """Read the email and the envelope :func:`write` wrote.

    The email read is held to what sending it may cost (``_render_budget``) before it is
    handed on.

    Raises:
        InvalidArgumentError: The data is not what :func:`write` writes, or the email holds
            more than sending one may cost.
    """
    found = fields(data, "the data", ("version", "message", "envelope"))
    version = found["version"]
    if type(version) is not int or version != _VERSION:
        refuse("version", f"is not {_VERSION}, the version this mailer reads")
    message = read_message(found["message"], "message")
    check_render_cost(message)
    return message, read_envelope(found["envelope"], "envelope")
