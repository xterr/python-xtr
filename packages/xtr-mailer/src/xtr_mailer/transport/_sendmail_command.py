"""A sendmail command read into its arguments, and the arguments one email is handed over with.

The command is split as a POSIX shell splits words — quotes and backslashes — but never run
through a shell: nothing in it is expanded, and nothing an email holds becomes an argument of
its own except where an argument is meant.
"""

from __future__ import annotations

import re
import shlex
from typing import TYPE_CHECKING, Final

from xtr_mailer._error_text import shown
from xtr_mailer.exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_mailer.envelope import Envelope

__all__ = ["delivery_arguments", "is_interactive", "piped_message", "sendmail_arguments"]

_INTERACTIVE: Final = "-bs"
_PIPED: Final = "-t"
_SENDER: Final = "-f"
_LONE_DOTS_KEPT: Final = frozenset({"-i", "-oi"})
_CONTROL: Final = re.compile(r"[\x00-\x1f\x7f]")


def sendmail_arguments(command: str) -> list[str]:
    """Split ``command`` into the program and its arguments, one of which picks the mode.

    Raises:
        InvalidArgumentError: ``command`` holds a control character, a quote it does not close,
            or neither ``-bs`` nor ``-t`` among its arguments.
    """
    if _CONTROL.search(command):
        raise InvalidArgumentError("The sendmail command must not contain control characters.")
    try:
        arguments = shlex.split(command)
    except ValueError:
        raise InvalidArgumentError(
            f'The sendmail command "{shown(command)}" does not parse: a quote or an escape is '
            "not closed."
        ) from None
    if not {_INTERACTIVE, _PIPED} & set(arguments[1:]):
        raise InvalidArgumentError(
            f'Unsupported sendmail command flags "{shown(command)}"; must be one of "-bs" or "-t" '
            "but can include additional flags."
        )
    return arguments


def is_interactive(arguments: Sequence[str]) -> bool:
    """Tell whether ``arguments`` run sendmail in SMTP mode, ``-bs``."""
    return _INTERACTIVE in arguments[1:]


def delivery_arguments(arguments: Sequence[str], envelope: Envelope) -> list[str]:
    """Return the arguments handing sendmail one email with ``envelope``.

    ``-t`` goes: the envelope names the recipients, after ``--`` so none is read as an
    option, rather than sendmail reading them from the headers — which would also deliver to
    a Bcc. The envelope's sender is given with ``-f`` unless the command gives one, written
    as one argument with it.

    Raises:
        InvalidArgumentError: The sender starts with a hyphen.
    """
    handed = [argument for argument in arguments if argument != _PIPED]
    if not any(argument.startswith(_SENDER) for argument in handed[1:]):
        sender = envelope.get_sender().get_encoded_address()
        if sender.startswith("-"):
            # Joined to -f it is one argument, but a sendmail parsing its arguments by hand
            # may take it for an option of its own.
            raise InvalidArgumentError(
                f'The envelope sender "{shown(sender)}" cannot be handed to sendmail: it starts '
                "with a hyphen, which sendmail could read as an option."
            )
        handed.append(f"{_SENDER}{sender}")
    handed.append("--")
    handed.extend(recipient.get_encoded_address() for recipient in envelope.get_recipients())
    return handed


def piped_message(message: bytes, arguments: Sequence[str]) -> bytes:
    """Return ``message`` as sendmail reads it: LF line endings, a leading dot doubled.

    Without ``-i`` or ``-oi``, sendmail takes a line holding a lone dot for the end of the
    message; a dot starting a line is doubled so none can end it early.
    """
    piped = message.replace(b"\r\n", b"\n")
    if _LONE_DOTS_KEPT.isdisjoint(arguments[1:]):
        piped = piped.replace(b"\n.", b"\n..")
    return piped
