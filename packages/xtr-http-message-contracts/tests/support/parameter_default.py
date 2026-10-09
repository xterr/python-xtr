"""Read the default an interface records for one of its optional parameters.

:func:`inspect.signature` answers out of an untyped mapping, so the default it
reports arrives as :data:`~typing.Any`. Narrowing it here, once, keeps every
test that asserts a default fully typed.
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["default_of"]


def default_of(method: Callable[..., object], parameter: str) -> object:
    """Return the default value ``method`` declares for ``parameter``.

    Args:
        method: The interface method to read, taken unbound off its protocol.
        parameter: The name of the parameter whose default is wanted.

    Returns:
        The default value. A parameter with no default reports
        :attr:`inspect.Parameter.empty`.
    """
    return cast("object", inspect.signature(method).parameters[parameter].default)
