# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportAttributeAccessIssue=false, reportAny=false, reportExplicitAny=false
# fsspec ships no type information, so every attribute reached on the wrapped
# filesystem is untyped to the checker; the directives above are confined to
# this one module, and every value is copied into a typed shape at the boundary.
"""The one place a filesystem is spoken to, turned into typed coroutines.

Every backend this package builds on is an fsspec filesystem, and fsspec speaks
two dialects: a synchronous one whose blocking calls must be pushed off the
event loop, and an asynchronous one whose real work hides behind ``_``-prefixed
coroutines that need a session opened first. This bridge is the seam that hides
that split: an adapter awaits :class:`FsspecBridge` methods and never learns
which dialect answered, and the untyped surface of fsspec is fenced to this file
so the rest of the package stays fully typed.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, final

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from fsspec import AbstractFileSystem

__all__ = ["FsspecBridge"]


@final
class FsspecBridge:
    """A typed async front to one fsspec filesystem, sync or asynchronous.

    The bridge owns nothing the filesystem does not already own except the
    session it opens on demand. It creates no filesystem — an adapter hands it
    one — and it does no I/O until a method is awaited, so constructing it is
    free. On an asynchronous filesystem the first awaited method opens the
    session once, under a lock, and ``close`` hands that session back to a
    per-backend closer; on a synchronous one every call is pushed to a worker
    thread and there is nothing to close.
    """

    __slots__ = (
        "_closed",
        "_closer",
        "_fs",
        "_session_created",
        "_session_lock",
        "_session_ready",
    )

    def __init__(
        self,
        filesystem: AbstractFileSystem,
        *,
        closer: Callable[[AbstractFileSystem], Awaitable[None]] | None = None,
    ) -> None:
        """Wrap a filesystem, remembering how to close any session it opens.

        Args:
            filesystem: The fsspec filesystem to speak to; kept as given, its
                dialect read from ``async_impl`` and ``asynchronous`` on each
                call so a caller may flip ``asynchronous`` before first use.
            closer: What to run once, on ``close``, when a session was opened —
                the S3 and object-store adapters pass the coroutine that shuts
                their client down. ``None`` means there is nothing to close.
        """
        self._fs = filesystem
        self._closer = closer
        self._session_lock = asyncio.Lock()
        self._session_ready = False
        self._session_created = False
        self._closed = False

    @property
    def _is_async(self) -> bool:
        """Whether calls must go through the ``_``-prefixed coroutines."""
        return bool(self._fs.async_impl and self._fs.asynchronous)  # ty: ignore[unresolved-attribute] -- fsspec ships no type information; asynchronous is set on the async filesystem

    async def _ensure_session(self) -> None:
        """Open the filesystem's session once, the first async call to need it.

        A filesystem without ``set_session`` (a plain asynchronous one) needs no
        session; one with it (s3fs, gcsfs) gets exactly one call however many
        coroutines race here, because the lock and the flag together let only
        the first through.
        """
        if self._session_ready:
            return
        async with self._session_lock:
            if self._session_ready:
                return
            set_session = getattr(self._fs, "set_session", None)
            if set_session is not None:
                _ = await set_session()
                self._session_created = True
            self._session_ready = True

    async def _dispatch(self, name: str, *args: object, **kwargs: object) -> Any:  # noqa: ANN401
        """Run one filesystem method the way its dialect requires.

        Args:
            name: The synchronous method name; the asynchronous dialect is
                reached at ``_`` + ``name``.
            *args: Positional arguments passed through unchanged.
            **kwargs: Keyword arguments passed through unchanged.

        Returns:
            Whatever the filesystem returned, untyped — fsspec ships no types, so
            this one seam is ``Any`` and every caller copies it into a typed
            shape at the boundary before it escapes the module.
        """
        if self._is_async:
            await self._ensure_session()
            return await getattr(self._fs, "_" + name)(*args, **kwargs)
        return await asyncio.to_thread(getattr(self._fs, name), *args, **kwargs)

    async def info(self, path: str) -> dict[str, object]:
        """Return what the filesystem knows about one path, copied out."""
        result = await self._dispatch("info", path)
        return dict(result)

    async def ls(self, path: str, *, detail: bool = True) -> list[dict[str, object]]:
        """List one directory in detail, each entry copied out."""
        result = await self._dispatch("ls", path, detail=detail)
        return [dict(entry) for entry in result]

    async def find(self, path: str, *, withdirs: bool) -> dict[str, dict[str, object]]:
        """Walk a tree, returning every path mapped to its detail, copied out."""
        result = await self._dispatch("find", path, withdirs=withdirs, detail=True)
        return {key: dict(value) for key, value in result.items()}

    async def cat_file(self, path: str, start: int | None = None, end: int | None = None) -> bytes:
        """Read a file, or the byte range ``[start, end)`` of it."""
        result = await self._dispatch("cat_file", path, start=start, end=end)
        return bytes(result)

    async def pipe_file(self, path: str, data: bytes, **kwargs: object) -> None:
        """Write ``data`` to ``path`` in one call."""
        _ = await self._dispatch("pipe_file", path, data, **kwargs)

    async def put_file(self, local_path: str, remote_path: str, **kwargs: object) -> None:
        """Upload a local file to ``remote_path``."""
        _ = await self._dispatch("put_file", local_path, remote_path, **kwargs)

    async def rm_file(self, path: str) -> None:
        """Remove one file."""
        _ = await self._dispatch("rm_file", path)

    async def rm(self, path: str, *, recursive: bool = True) -> None:
        """Remove a path, its whole tree by default."""
        _ = await self._dispatch("rm", path, recursive=recursive)

    async def mkdir(self, path: str, *, create_parents: bool = True) -> None:
        """Make a directory, its parents too by default."""
        _ = await self._dispatch("mkdir", path, create_parents=create_parents)

    async def cp_file(self, src: str, dst: str, **kwargs: object) -> None:
        """Copy one file within the filesystem."""
        _ = await self._dispatch("cp_file", src, dst, **kwargs)

    async def mv(self, src: str, dst: str) -> None:
        """Move one file, falling back to copy-then-delete where ``_mv`` is absent.

        The synchronous dialect has ``mv``; the asynchronous base does not
        expose ``_mv``, so there the move is a copy followed by a delete —
        exactly what an object store does anyway.
        """
        if self._is_async:
            await self._ensure_session()
            mv_method = getattr(self._fs, "_mv", None)
            if mv_method is not None:
                _ = await mv_method(src, dst)
                return
            await self.cp_file(src, dst)
            await self.rm_file(src)
            return
        _ = await asyncio.to_thread(self._fs.mv, src, dst)

    async def sign(self, path: str, expiration: int) -> str:
        """Return a signed URL for ``path``, valid ``expiration`` seconds.

        The asynchronous dialect signs through ``_url`` when a backend provides
        it (s3fs, gcsfs); otherwise, and for the synchronous dialect, the
        blocking ``sign`` is pushed to a worker thread.
        """
        if self._is_async:
            await self._ensure_session()
            url_method = getattr(self._fs, "_url", None)
            if url_method is not None:
                return str(await url_method(path, expires=expiration))
        return str(await asyncio.to_thread(self._fs.sign, path, expiration))

    async def exists(self, path: str) -> bool:
        """Whether the path exists."""
        return bool(await self._dispatch("exists", path))

    async def call(self, name: str, *args: object, **kwargs: object) -> object:
        """Run a backend-specific method by name, dispatched like the rest.

        The escape hatch for what only one backend does — an ACL read, a chmod —
        so those adapters need no second seam. The return is untyped; the caller
        parses it.
        """
        return await self._dispatch(name, *args, **kwargs)

    async def close(self) -> None:
        """Close the session, once, if one was opened; safe to call again."""
        if self._closed:
            return
        self._closed = True
        if self._closer is not None and self._session_created:
            await self._closer(self._fs)
