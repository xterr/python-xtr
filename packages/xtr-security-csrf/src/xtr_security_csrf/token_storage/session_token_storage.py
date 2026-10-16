"""A token storage that keeps its tokens in the session a request carries."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

from typing_extensions import override

from xtr_security_csrf.exception import TokenNotFoundError

from .clearable_token_storage_interface import ClearableTokenStorageInterface

if TYPE_CHECKING:
    from xtr_http_foundation import SessionInterface

__all__ = ["SessionTokenStorage"]


@final
class SessionTokenStorage(ClearableTokenStorageInterface):
    """Keeps token values in the session, under the id they answer for.

    Each value lives under ``<namespace>/<token_id>``: the namespace keeps
    the tokens out of the attributes the rest of the application keeps in
    the same session, and lets two applications sharing one session keep
    their tokens apart.

    The storage also keeps the list of its ids under the namespace key
    itself. The session offers no way to walk the attributes it carries, so
    the list is what ``clear()`` drops them from — every token this storage
    minted, and nothing the rest of the session holds. A value written
    under the namespace by something else than this storage is not in the
    list, and survives a clear.
    """

    __slots__ = ("_namespace", "_session")

    def __init__(self, session: SessionInterface, namespace: str = "_csrf") -> None:
        """Record the session the tokens travel in, and their namespace.

        Args:
            session: The session whose attributes carry the tokens.
            namespace: The prefix every stored id carries.
        """
        self._session = session
        self._namespace = namespace

    @override
    async def get_token(self, token_id: str) -> str:
        """Return the value stored under ``token_id``.

        Raises:
            TokenNotFoundError: When no value is stored under the id.
        """
        name = self._key(token_id)
        if not await self._session.has(name):
            raise TokenNotFoundError(token_id)
        return str(await self._session.get(name))

    @override
    async def set_token(self, token_id: str, token: str) -> None:
        """Store ``token`` under ``token_id``, and remember the id."""
        await self._session.set(self._key(token_id), token)
        await self._remember(token_id)

    @override
    async def has_token(self, token_id: str) -> bool:
        """Tell whether a value is stored under ``token_id``."""
        return await self._session.has(self._key(token_id))

    @override
    async def remove_token(self, token_id: str) -> str | None:
        """Drop the value under ``token_id``, returning what it held."""
        value = await self._session.remove(self._key(token_id))
        await self._forget(token_id)
        return None if value is None else str(value)

    @override
    async def clear(self) -> None:
        """Drop every token this storage minted, and nothing else.

        The ids come from the list kept under the namespace key, so the
        clear is complete across the requests that minted them — a token
        stored two requests ago goes with one stored now. The session
        strategy calls this when a re-authentication rotates the session:
        the tokens minted under the old one must not answer for the new.
        """
        for token_id in await self._stored_ids():
            _ = await self._session.remove(self._key(token_id))
        _ = await self._session.remove(self._namespace)

    def _key(self, token_id: str) -> str:
        """Return the name the value for ``token_id`` is stored under."""
        return f"{self._namespace}/{token_id}"

    async def _stored_ids(self) -> tuple[str, ...]:
        """Return every id this storage has minted a token under."""
        ids = await self._session.get(self._namespace)
        if not isinstance(ids, list):
            return ()
        # The list is written by this class, of the ids it minted; the cast
        # says so once rather than at every element the loop reads.
        return tuple(cast("list[str]", ids))

    async def _remember(self, token_id: str) -> None:
        """Add ``token_id`` to the ids a ``clear()`` drops, if it is not there."""
        ids = await self._stored_ids()
        if token_id not in ids:
            await self._session.set(self._namespace, [*ids, token_id])

    async def _forget(self, token_id: str) -> None:
        """Take ``token_id`` out of the ids a ``clear()`` drops."""
        ids = await self._stored_ids()
        if token_id not in ids:
            return
        remaining = [stored for stored in ids if stored != token_id]
        if remaining:
            await self._session.set(self._namespace, remaining)
        else:
            _ = await self._session.remove(self._namespace)
