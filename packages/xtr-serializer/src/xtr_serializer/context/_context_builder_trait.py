"""What every context builder shares: the options it holds, and setting one on a new builder."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Self, cast

if TYPE_CHECKING:
    from .context import Context

__all__ = ["ContextBuilderTrait"]


class ContextBuilderTrait:
    """The options a context builder holds, and the one way it sets an option: on a new builder.

    A base rather than a builder of its own: a builder adds the typed methods for the options of
    its step, each setting one key through :meth:`_with`. Immutable: setting an option returns a
    new builder and leaves this one as it was, so a builder holding an application's defaults can
    be extended for one call without that call's options reaching the next.

    Nothing a caller does afterwards reaches a builder: the dictionaries, lists, tuples and sets
    in the context it starts from are copied, at any depth, and so are those in what
    :meth:`to_dict` returns. Any other value is handed on as it is — an object a validator reads
    from the context stays that object.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_context",)

    def __init__(self, context: Context | None = None) -> None:
        """Start from the options in ``context``, or from none.

        Args:
            context: The options to start from — an application's defaults, or what another
                builder built. Copied, so a later change to it does not reach this builder.
        """
        self._context: dict[str, object] = {
            key: _copied(value) for key, value in (context or {}).items()
        }

    def to_dict(self) -> dict[str, object]:
        """Return the options built so far, as a new dictionary to pass to a call."""
        return {key: _copied(value) for key, value in self._context.items()}

    def _with(self, key: str, value: object) -> Self:
        """Return a builder holding these options and ``value`` under ``key``."""
        return type(self)({**self._context, key: value})


def _copied(value: object) -> object:
    """Return ``value`` with every dictionary, list, tuple and set in it copied, at any depth.

    Those hold the options' own data, which their owner may go on changing. Anything else is
    shared: a set's items are hashable, and an object was handed over to be used as it is.
    """
    if isinstance(value, dict):
        mapping = cast("dict[object, object]", value)
        return {key: _copied(item) for key, item in mapping.items()}
    if isinstance(value, list | tuple):
        items = [_copied(item) for item in cast("list[object] | tuple[object, ...]", value)]
        return items if isinstance(value, list) else tuple(items)
    if isinstance(value, set):
        return set(cast("set[object]", value))
    return value
