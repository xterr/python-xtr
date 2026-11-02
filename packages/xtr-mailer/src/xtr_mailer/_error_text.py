"""Puts what was given into an error message without letting it break the message.

An error ends up in a log: a line break, a null byte or a lone surrogate taken from what was
given must not reach it as such, so each is shown escaped, as ``repr`` shows it — and a long
value is cut short, so an error repeats enough to find it, never a whole header's worth.

A class an error names is named by where it is imported from, so the name can be searched for.
"""

from __future__ import annotations

from typing import Final

__all__ = ["shown", "type_name"]

_SHOWN_LENGTH: Final = 64


def shown(value: str) -> str:
    """Show the start of ``value`` as ``repr`` does, without its quotes, ``…`` if it goes on."""
    return repr(value[:_SHOWN_LENGTH])[1:-1] + ("…" if len(value) > _SHOWN_LENGTH else "")


def type_name(cls: type) -> str:
    """Name ``cls`` by its package when it is a mailer class, else by its module.

    Each mailer class has a file of its own named after it, and is imported from the package
    that file sits in: ``xtr_mailer.transport.Transports``, not ``...transports.Transports``.
    """
    module = cls.__module__
    if module.startswith("xtr_mailer."):
        module = module.rpartition(".")[0]
    return f"{module}.{cls.__qualname__}"
