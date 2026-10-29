"""What every context builder shares: the options it holds, and setting one on a new builder."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Final, Self, cast

from xtr_serializer.exception import InvalidArgumentError

if TYPE_CHECKING:
    from .context import Context

__all__ = ["ContextBuilderTrait"]

# Far deeper than any context nests its options. The copy takes a call per level, and stopping
# here keeps it clear of the interpreter's own limit, which would end it with a RecursionError.
_MAX_DEPTH: Final = 100

# The containers that hold the options' own data. Only these exact types: a subclass is an object
# of its own, which a validator may read by its attributes.
_COPIED: Final = frozenset({dict, list, tuple, set})


class ContextBuilderTrait:
    """The options a context builder holds, and the one way it sets an option: on a new builder.

    A base rather than a builder of its own: a builder adds the typed methods for the options of
    its step, each setting one key through :meth:`_with`. Immutable: setting an option returns a
    new builder and leaves this one as it was, so a builder holding an application's defaults can
    be extended for one call without that call's options reaching the next.

    Nothing a caller does afterwards to the plain dictionaries, lists, tuples and sets in the
    context a builder starts from reaches it, nor to those in what :meth:`to_dict` returns: they
    are copied. Only those four types are; any other value is handed on as it is, a subclass of
    one of them included — a named tuple, an ordered or a default dictionary is an object a
    validator reads from the context, and it stays that object. A copy keeps the shape of what it
    copies: a container held in two places is one copy held in both, and one that holds itself
    holds its copy. Containers nested more than 100 levels deep are refused.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_context",)

    def __init__(self, context: Context | None = None) -> None:
        """Start from the options in ``context``, or from none.

        Args:
            context: The options to start from — an application's defaults, or what another
                builder built. Copied, so a later change to it does not reach this builder.

        Raises:
            InvalidArgumentError: When ``context`` nests its containers more than 100 levels
                deep.
        """
        self._context: dict[str, object] = _copied(context or {})

    def to_dict(self) -> dict[str, object]:
        """Return the options built so far, as a new dictionary to pass to a call."""
        return _copied(self._context)

    def _with(self, key: str, value: object) -> Self:
        """Return a builder holding these options and ``value`` under ``key``."""
        return type(self)({**self._context, key: value})


def _copied(context: Context) -> dict[str, object]:
    """Return the options of ``context`` in a new dictionary, each copied by :func:`_copy`."""
    options: dict[str, object] = {}
    copies: dict[int, object] = {id(context): options}  # a context may hold itself, too
    for key, value in context.items():
        options[key] = _copy(value, copies, 1)
    return options


def _copy(value: object, copies: dict[int, object], depth: int) -> object:
    """Return ``value`` with every plain dictionary, list, tuple and set in it copied.

    Those hold the options' own data, which their owner may go on changing. Anything else is
    shared: a set's items are hashable, and an object was handed over to be used as it is.
    ``copies`` holds the copy of each container met so far, by the identity of the original, so
    one met again is not copied twice; ``depth`` is how many containers ``value`` sits in.
    """
    kind = type(value)
    if kind not in _COPIED:
        return value
    if (copy := copies.get(id(value))) is not None:
        return copy
    if depth > _MAX_DEPTH:
        raise InvalidArgumentError(
            f"a context must not nest its containers more than {_MAX_DEPTH} levels deep"
        )
    if kind is dict:
        mapping: dict[object, object] = {}
        copies[id(value)] = mapping
        for key, item in cast("dict[object, object]", value).items():
            mapping[key] = _copy(item, copies, depth + 1)
        return mapping
    if kind is list:
        items: list[object] = []
        copies[id(value)] = items
        items.extend(_copy(item, copies, depth + 1) for item in cast("list[object]", value))
        return items
    if kind is set:
        copies[id(value)] = copy = set(cast("set[object]", value))
        return copy
    # A tuple is made from its items, so it is stored once they are copied — unless one of them
    # holds it, and copying that item met the tuple again and stored its copy already.
    members = [_copy(item, copies, depth + 1) for item in cast("tuple[object, ...]", value)]
    return copies.setdefault(id(value), tuple(members))
