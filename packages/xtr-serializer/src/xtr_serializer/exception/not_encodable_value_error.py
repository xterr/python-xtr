"""Plain data could not be written as text, or text could not be read back."""

from __future__ import annotations

from .unexpected_value_error import UnexpectedValueError

__all__ = ["NotEncodableValueError"]


class NotEncodableValueError(UnexpectedValueError):
    """Plain data has no form in the requested format, or text is not valid in it.

    The encoder's error, on either side of it: writing a float JSON has no form
    for, such as infinity, or reading text that is not valid JSON.
    Raised rather than written approximately, because text that does not say
    exactly what was meant is read back as something else.
    """
