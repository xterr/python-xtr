"""What puts a context together with the type of each option checked."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["ContextBuilderInterface"]


@runtime_checkable
class ContextBuilderInterface(Protocol):
    """Puts a context together one option at a time, each through a typed method.

    A context is a plain mapping: a misspelled key in it, or a value of the wrong type, goes
    unnoticed until the step that should read it — and a key no step reads goes unnoticed for
    good. A builder makes each option a method whose name and argument type a type checker
    knows, and hands back the mapping to pass.
    """

    def to_dict(self) -> dict[str, object]:
        """Return the context built so far, as a new dictionary to pass to a call."""
        ...
