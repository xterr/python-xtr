"""What a scope answers to."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from typing_extensions import override

__all__ = ["ScopeEntityInterface"]


@runtime_checkable
class ScopeEntityInterface(Protocol):
    """One permission a token may carry, named by its identifier.

    A scope is the thinnest entity here: the identifier is the whole of it, and
    everything the protocol does with a scope — parse it out of a request,
    finalise the set, write it into a token or a response — works on that
    identifier alone. An implementation is free to hang a description, a label
    or a row id off its own class; nothing in the library reads them.

    Reading a scope gives its identifier, which is what lets a set of them be
    written out as JSON with ``json.dumps(scopes, default=str)`` — the form the
    encrypted payloads and the token responses use.
    """

    def get_identifier(self) -> str:
        """Return the identifier this scope is named by."""
        ...

    @override
    def __str__(self) -> str:
        """Return the identifier, so a scope reads and serialises as its name."""
        ...
