"""Puts what was given into an error message without letting it break the message.

An error ends up in a log: a line break, a null byte or a lone surrogate taken from what was
given must not reach it as such, so each is shown escaped, as ``repr`` shows it — and a long
value is cut short, so an error repeats enough to find it, never a whole header's worth.

A class an error names is named by where it is imported from, so the name can be searched for.

A DSN option's value is quoted only when it is one plain word: the query string runs to the end
of the DSN, so a second DSN glued on by a missing space would bring its credentials along.
"""

from __future__ import annotations

import re
from typing import Final

__all__ = ["option_value", "shown", "type_name"]

_SHOWN_LENGTH: Final = 64
_PLAIN_WORD: Final = re.compile(r"[A-Za-z0-9.+_-]{0,40}")


def shown(value: str) -> str:
    """Show the start of ``value`` as ``repr`` does, without its quotes, ``…`` if it goes on."""
    return repr(value[:_SHOWN_LENGTH])[1:-1] + ("…" if len(value) > _SHOWN_LENGTH else "")


def option_value(value: str) -> str | None:
    """Return a DSN option's ``value`` when an error may quote it — a plain word — else ``None``."""
    return value if _PLAIN_WORD.fullmatch(value) else None


def type_name(cls: type) -> str:
    """Name ``cls`` by its package when it is a mailer or a mime class, else by its module.

    Each mailer and mime class has a file of its own named after it, and is imported from the
    package that file sits in: ``xtr_mailer.transport.Transports``, not
    ``...transports.Transports``.
    """
    module = cls.__module__
    if module.startswith(("xtr_mailer.", "xtr_mime.")):
        module = module.rpartition(".")[0]
    return f"{module}.{cls.__qualname__}"
