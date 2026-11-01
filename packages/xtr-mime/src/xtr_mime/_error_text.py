"""Puts what was given into an error message without letting it break the message.

An error ends up in a log: a line break, a null byte or a lone surrogate taken from what was
given must not reach it as such, so each is shown escaped, as ``repr`` shows it.
"""

from __future__ import annotations

import codecs

from .exception import InvalidArgumentError

__all__ = ["body_charset_error", "check_charset", "escaped"]


def escaped(value: str) -> str:
    """Show ``value`` as ``repr`` does, without its quotes."""
    return repr(value)[1:-1]


def body_charset_error(charset: str, error: LookupError | ValueError) -> InvalidArgumentError:
    """Return the error for a body that cannot be read, or written, in ``charset``.

    A codec's own message shows the characters and bytes it names escaped already; the one
    for an unknown charset, or for a null byte in its name, may repeat the charset as given.
    """
    reason = str(error) if isinstance(error, UnicodeError) else escaped(str(error))
    return InvalidArgumentError(f'The body is not "{escaped(charset)}" text: {reason}.')


def check_charset(charset: str) -> None:
    """Refuse a charset no codec goes by.

    Raises:
        InvalidArgumentError: There is none; a null byte in the name makes the codecs raise
            ``ValueError`` rather than ``LookupError``.
    """
    try:
        _ = codecs.lookup(charset)
    except (LookupError, ValueError) as error:
        raise body_charset_error(charset, error) from error
