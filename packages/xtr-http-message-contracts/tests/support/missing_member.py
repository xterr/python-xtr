"""Take one member off a fake, so that every member can be shown to be required.

Dropping a member by hand would mean writing out a near-copy of each fake once
per member it carries. The thirteen interfaces declare seventy-seven members
between them, and inheritance compounds that — a server request fake carries
thirty, its own thirteen on top of the six a request and the eleven a message
bring — so the near-copies would come to a hundred and fifteen. This builds
each one instead, from the fake's own members minus the one named.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["members_of", "without"]


class _Bare:
    """Declares nothing at all: whatever is in it, the interpreter put there."""


# What a class carries because it is a class — the module it was declared in,
# its qualified name, where its body starts, and the two slots ``type()``
# refuses to be handed a second copy of. Nobody declared any of them, and the
# set follows whatever the running interpreter adds.
_PLUMBING = frozenset(vars(_Bare))

# A name ``object`` itself answers to proves nothing: every object has it, so a
# protocol asking for it is satisfied whether the fake declares it or not.
# ``UriInterface.__str__`` is the only such member across the interfaces, so it
# is the only one the parametrization has to pass over.
_ALWAYS_THERE = frozenset(dir(object))


def members_of(fake: type) -> frozenset[str]:
    """Return the members of ``fake`` whose absence an ``isinstance`` check can see."""
    return frozenset(_namespace(fake)) - _ALWAYS_THERE


def without(fake: type, member: str) -> type[object]:
    """Return a class carrying everything ``fake`` does but ``member``."""
    namespace = _namespace(fake)
    del namespace[member]
    built: type[object] = type(f"{fake.__name__}_without_{member}", (), namespace)
    return built


def _namespace(fake: type) -> dict[str, object]:
    """Return every member ``fake`` and its bases define, the bases' first."""
    collected: dict[str, object] = {}
    for klass in reversed(fake.__mro__):
        if klass is object:
            continue
        defined = cast("Mapping[str, object]", vars(klass))
        collected.update({name: value for name, value in defined.items() if name not in _PLUMBING})
    return collected
