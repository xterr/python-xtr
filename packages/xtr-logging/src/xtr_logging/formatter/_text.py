"""Turning a logged value into text, whatever the value does."""

from __future__ import annotations

__all__ = ["class_name", "describe", "safe_str"]


def class_name(value: object) -> str:
    """Return the name of ``value``'s class, qualified by its module unless built in."""
    kind = type(value)
    if kind.__module__ == "builtins":
        return kind.__qualname__
    return f"{kind.__module__}.{kind.__qualname__}"


def safe_str(value: object) -> str:
    """Return ``str(value)``, or a stand-in naming its class when ``__str__`` raises.

    A value is data from the caller, never a reason for a log call to fail:
    a detached model or a lazy proxy may raise from ``__str__``.
    """
    try:
        return str(value)
    except Exception:  # noqa: BLE001 — whatever it raises, the record is still written
        return f"[unprintable {class_name(value)}]"


def describe(value: object) -> str:
    """Use ``str()`` when the class defines one; otherwise name the class."""
    kind = type(value)
    if kind.__str__ is not object.__str__ or kind.__repr__ is not object.__repr__:
        return safe_str(value)
    return f"[object {class_name(value)}]"
