"""A listing that is a plan for reading entries, not the entries themselves."""

from __future__ import annotations

from typing import TYPE_CHECKING, Generic, Protocol, TypeVar, final

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

__all__ = ["DirectoryListing"]


class _HasPath(Protocol):
    """Anything a listing can be ordered by: an entry that knows where it is."""

    @property
    def path(self) -> str:
        """Where the entry is, relative to the storage's root."""
        ...


T = TypeVar("T")
R = TypeVar("R")
PathT = TypeVar("PathT", bound=_HasPath)


@final
class DirectoryListing(Generic[T]):
    """Entries a storage would yield, described rather than fetched.

    A directory on an object store can hold more entries than fit in memory,
    and a caller usually wants a handful of them. So this holds no entries: it
    holds a *source factory* — a zero-argument callable that starts a fresh
    read — and :meth:`filter` and :meth:`map` return a new listing wrapping
    that source in another step. Nothing is read, no backend is called and no
    error is raised until something iterates.

    ```python
    listing = storage.list_contents("photos", deep=True)  # no call made yet
    names = listing.filter(lambda entry: entry.is_file).map(lambda entry: entry.path)
    async for name in names:  # the backend is read here, once
        print(name)
    ```

    Iterating twice calls the source factory twice, which re-reads the backend:
    a listing is a question, and asking it again may rightly get a new answer.
    Hold :meth:`to_list` instead when one answer must serve twice.

    Two operations cannot stay lazy. :meth:`sort_by_path` has to see every
    entry before it can yield the first, and :meth:`to_list` exists to gather
    them; both read the whole listing into memory when they run.
    """

    __slots__ = ("_source",)

    _source: Callable[[], AsyncIterator[T]]

    def __init__(self, source: Callable[[], AsyncIterator[T]]) -> None:
        """Take the factory that starts one read of the entries.

        Args:
            source: Called with no arguments each time iteration begins, and
                expected to return a fresh iterator. A factory rather than an
                iterator so the listing can be read more than once, and so
                building it costs nothing.
        """
        self._source = source

    def __aiter__(self) -> AsyncIterator[T]:
        """Start one read, by asking the source factory for a fresh iterator."""
        return self._source()

    def filter(self, predicate: Callable[[T], bool]) -> DirectoryListing[T]:
        """Return the entries ``predicate`` accepts, deciding as they arrive.

        Nothing is read here: the returned listing remembers the question and
        asks it of each entry while it is being iterated.

        Args:
            predicate: Answers whether one entry belongs in the result.

        Returns:
            A new listing; this one is unchanged.
        """
        source = self._source

        async def filtered() -> AsyncIterator[T]:
            async for entry in source():
                if predicate(entry):
                    yield entry

        return DirectoryListing(filtered)

    def map(self, transform: Callable[[T], R]) -> DirectoryListing[R]:
        """Return each entry as ``transform`` describes it, one at a time.

        Nothing is read here either — the transformation runs per entry during
        iteration, so a listing of a million files costs one entry of memory.

        Args:
            transform: Turns one entry into whatever the caller wants instead,
                a path or a payload of its own.

        Returns:
            A new listing over the transformed entries; this one is unchanged.
        """
        source = self._source

        async def mapped() -> AsyncIterator[R]:
            async for entry in source():
                yield transform(entry)

        return DirectoryListing(mapped)

    def sort_by_path(self: DirectoryListing[PathT]) -> DirectoryListing[PathT]:
        """Return the entries ordered by path — the one step that cannot stream.

        Backends list in whatever order suits them, and code that compares two
        listings, or shows one to a person, needs an order it chose. The last
        entry may be the first alphabetically, so the returned listing reads
        the whole source into memory before it yields anything. Keep it late in
        a chain: a :meth:`filter` placed before it is what bounds the cost.

        Returns:
            A new listing which, each time it is iterated, reads the source in
            full and yields its entries ordered by :attr:`path`.
        """
        source = self._source

        async def in_path_order() -> AsyncIterator[PathT]:
            entries = [entry async for entry in source()]
            entries.sort(key=lambda entry: entry.path)

            for entry in entries:
                yield entry

        return DirectoryListing(in_path_order)

    async def to_list(self) -> list[T]:
        """Read every entry and return them, for when one answer must serve twice.

        This is where a listing stops being a plan: it reads the source to the
        end and keeps the result, so nothing else has to worry that iterating
        again would ask the backend again.

        Returns:
            Every entry, in the order the listing yields them.
        """
        return [entry async for entry in self._source()]
