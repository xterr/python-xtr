"""What is built once per type, kept for the types used last, and shared between threads."""

from __future__ import annotations

from threading import RLock, get_ident
from typing import TYPE_CHECKING, Final, Generic, TypeVar, cast, final, get_args

from typing_extensions import override

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["TypeCache"]

_V = TypeVar("_V")

# How many types a cache keeps the value of. A type expression built per call, such as
# Annotated[int, Field(ge=0)], is a new key each time; the least recently used goes first.
_CACHE_SIZE: Final = 256


@final
class _Key:
    """A type's key, hashed once as it is made, and compared without letting the type raise.

    A type's own code may hash or compare it differently, or raise, from one call to the next.
    Hashed once, a kept key is found, moved and evicted by the hash it was kept under, never
    hashing the type again; compared, a key whose type's code raises is taken for another, so a
    lookup of any type never fails for a key kept before it.
    """

    __slots__ = ("_hash", "_key")

    def __init__(self, key: object) -> None:
        self._key = key
        self._hash = hash(key)

    @override
    def __hash__(self) -> int:
        return self._hash

    @override
    def __eq__(self, other: object) -> bool:
        try:
            return self._key == cast("_Key", other)._key  # only keys are kept
        except Exception:  # noqa: BLE001 - whatever the type's own code raises makes them differ
            return False


@final
class _OwnedLock:
    """A lock telling which thread holds it, so that the calls that thread makes back know it.

    A cache changes its table holding the lock, and changing it compares keys, which runs the
    types' own code: that code, or a signal handler or a finalizer run meanwhile, may call the
    cache back on the same thread, which must then not change the table too.
    """

    __slots__ = ("_lock", "owner")

    def __init__(self) -> None:
        # Re-entrant all the same: a call back made just as the lock is taken or let go finds no
        # owner yet, or none any more, and takes it again, changing the table between changes.
        self._lock = RLock()
        # Set and cleared only by the thread holding the lock: a thread finds itself here only
        # while it holds it, so reading it takes no lock.
        self.owner: int | None = None

    def __enter__(self) -> None:
        _ = self._lock.acquire()
        self.owner = get_ident()

    def __exit__(self, *_: object) -> None:
        self.owner = None
        self._lock.release()


@final
class TypeCache(Generic[_V]):
    """The values built for the types used last, each in a scope, such as a format.

    A union's members count in the order written, as pydantic tries them in that order. Threads
    may share a cache. A value built is never ``None``.
    """

    __slots__ = ("_kept", "_lock")

    def __init__(self) -> None:
        # Oldest use first: a type used again is moved to the end.
        self._kept: dict[_Key, _V] = {}
        self._lock = _OwnedLock()

    def __len__(self) -> int:
        """Give how many types the cache keeps a value of."""
        return len(self._kept)

    def get(self, type_: object, build_factory: Callable[[], _V], scope: str | None = None) -> _V:
        """Return the value kept for ``type_`` in ``scope``, calling ``build_factory`` on first use.

        Keying a type runs its own code — reading its class to take it apart, hashing it — which
        may raise, as may a type nested deeper than keying it can go. Such a type is not kept but
        built every time. A type that raises only later, as it is compared with another kept or
        asked for its hash again, is no longer found: it is built again, and its kept value goes
        when its turn comes.

        Looking a type up, moving it to the end, keeping it and evicting the oldest are done
        holding a lock, so that no thread finds the cache half changed. Building is not, as it is
        slow and runs the application's code: two threads may build for the same type at once,
        and the value kept last stays. Only a call made back by the thread holding the lock
        builds under it.

        Comparing keys under the lock runs the types' own code, which may use the cache in turn,
        as may a signal handler or a finalizer run meanwhile. Such a call only looks the type up —
        a table changed while a lookup compares its keys may have that lookup start over for ever —
        and builds for a type it does not find without keeping it. A comparison that waits for
        another thread can deadlock, should that thread be waiting for this lock; so can one using
        another cache, should a thread holding that one's lock be waiting for this one.
        """
        try:
            key = _Key((scope, _key_of(type_)))
        except Exception:  # noqa: BLE001 - whatever the type's own code raises leaves it unkept
            return build_factory()
        if self._lock.owner == get_ident():
            # Called back from under the lock: the table is looked into, so it is only read.
            kept = self._kept.get(key)
            return build_factory() if kept is None else kept
        with self._lock:
            kept = self._kept.pop(key, None)
            if kept is not None:
                self._keep(key, kept)
                return kept
        value = build_factory()
        with self._lock:
            self._keep(key, value)
        return value

    def _keep(self, key: _Key, value: _V) -> None:
        """Keep ``value`` as used last, evicting the oldest while more than the bound are kept."""
        self._kept[key] = value
        while len(self._kept) > _CACHE_SIZE:
            _ = self._kept.pop(next(iter(self._kept)), None)


def _key_of(type_: object) -> object:
    """Key ``type_`` by its arguments in order, which a union's equality leaves out."""
    arguments: tuple[object, ...] = get_args(type_)
    return (type_, tuple(_key_of(argument) for argument in arguments))
