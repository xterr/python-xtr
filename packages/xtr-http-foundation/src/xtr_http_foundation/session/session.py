"""The state a request carries between requests: attributes under an ID."""

from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final, Self, TypeGuard, final

from typing_extensions import override

from xtr_http_foundation.response_cookie import cookie_header_value

from .session_cookie_config import SessionCookieConfig
from .session_interface import SessionInterface

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

    from .storage.session_storage_interface import SessionStorageInterface

__all__ = ["Session"]

# A session ID is 48 lowercase hex characters — 192 bits — which keeps it
# inside the key alphabet every storage accepts: letters, digits and the
# underscore up to 64 characters, per the caching contracts, because the ID
# becomes the key its entry is stored under. An ID that arrives in a cookie
# is taken between 32 and 128 characters, so a longer or an older generation
# still reattaches; anything else is no ID at all.
_ID_PATTERN: Final = re.compile(r"^[0-9a-f]{32,128}$")

# The cookie every session travels in when the application says nothing. One
# shared instance, because the config is frozen: nothing a request does can
# change it, and building a fresh one per default would only say so twice.
_DEFAULT_COOKIE: Final = SessionCookieConfig()


@final
class Session(SessionInterface):
    """The attributes a stateful request carries, under an ID the cookie reattaches.

    A session is a mapping of names to values and an ID; the mapping lives in
    memory for the request and in the storage between requests, and the ID
    is how the two are told apart. The cookie carries the ID to the client
    and back, and nothing else — the values never leave the server.

    Nothing is read from the storage until the first attribute is asked for,
    so a request that never touches its session costs nothing; and a session
    on the memory storage performs no I/O at all, ever.
    """

    __slots__ = (
        "_attributes",
        "_cookie",
        "_id",
        "_id_changed",
        "_id_generated",
        "_started",
        "_storage",
    )

    def __init__(
        self,
        storage: SessionStorageInterface,
        *,
        cookie: SessionCookieConfig = _DEFAULT_COOKIE,
        cookie_value: str | None = None,
    ) -> None:
        """Record where the attributes are kept, and decide the ID.

        Args:
            storage: Where the attributes are kept between requests.
            cookie: The shape of the cookie that carries the ID.
            cookie_value: The ID cookie the request carried, as the request
                read it. One that is no readable ID — misspelled, upper
                case, somebody else's format — is treated as no cookie at
                all: the stranger's cookie is theirs to misspell, so a new
                ID is made and nothing is ever stored under the unreadable
                one.
        """
        self._storage = storage
        self._cookie = cookie
        self._attributes: dict[str, object] = {}
        self._started = False
        self._id_changed = False

        if _is_session_id(cookie_value):
            self._id = cookie_value
            self._id_generated = False
        else:
            self._id = secrets.token_hex(24)
            self._id_generated = True

    @classmethod
    def from_request(
        cls,
        request: ServerRequestInterface,
        storage: SessionStorageInterface,
        *,
        cookie: SessionCookieConfig = _DEFAULT_COOKIE,
    ) -> Self:
        """Build the session a request reattaches, reading the ID cookie it carried.

        The one request-to-session path: the wiring, the firewall glue and
        the tests all come through here, because the cookie the request
        carried is the request's business to read.

        Args:
            request: The request that arrived.
            storage: Where the attributes are kept between requests.
            cookie: The shape of the cookie that carries the ID; its name
                is the name read from the request.

        Returns:
            The session for the request — started or not, since nothing is
            read until the first attribute is asked for.
        """
        return cls(
            storage,
            cookie=cookie,
            cookie_value=request.get_cookie_params().get(cookie.name),
        )

    @override
    async def start(self) -> None:
        """Load the attributes the storage holds under the ID.

        Every member that touches the attributes starts the session first,
        so a caller rarely needs this one; it is the way to pay for the
        session up front, before a response is half-written.

        Raises:
            SessionError: When the storage fails to load the session.
        """
        if self._started:
            return

        stored = await self._storage.read(self._id)
        if stored is not None:
            self._attributes.update(stored)
        self._started = True

    @override
    def is_started(self) -> bool:
        """Tell whether the attributes were loaded for this request."""
        return self._started

    @override
    async def get(self, name: str, default: object | None = None) -> object | None:
        """Return the attribute under ``name``, or ``default`` when there is none."""
        await self.start()
        return self._attributes.get(name, default)

    @override
    async def set(self, name: str, value: object) -> None:
        """Set the attribute under ``name`` to ``value``, as it was given.

        What the value must be to survive the storage is the storage's own
        contract, and it is heard at ``save()``.
        """
        await self.start()
        self._attributes[name] = value

    @override
    async def has(self, name: str) -> bool:
        """Tell whether the session carries an attribute under ``name``."""
        await self.start()
        return name in self._attributes

    @override
    async def remove(self, name: str) -> object | None:
        """Drop the attribute under ``name``, returning the value it had.

        Returning what was removed saves a caller that wants the value —
        an error message shown once, a path redirected to — from reading
        it first and dropping it after.
        """
        await self.start()
        return self._attributes.pop(name, None)

    @override
    async def clear(self) -> None:
        """Drop every attribute, in memory; the stored entry follows at ``save()``.

        Starting first means the attributes still stored are loaded and
        dropped with the rest, so a session cleared and saved leaves
        nothing stored either — ``save()`` of an empty session deletes the
        entry.
        """
        await self.start()
        self._attributes.clear()

    @override
    async def migrate(self, destroy_old: bool = False) -> None:
        """Carry the attributes to a new ID, keeping every one of them.

        The session is started first, so the attributes still stored under
        the old ID travel with it. The old entry is deleted only when
        ``destroy_old`` says so — a session that may still be open in
        another request keeps its entry until the one rotating the ID
        decides the old one is dead.

        Args:
            destroy_old: Whether to delete the entry stored under the old ID.
        """
        await self.start()

        old_id = self._id
        self._id = secrets.token_hex(24)
        self._id_changed = True

        if destroy_old:
            await self._storage.delete(old_id)

    @override
    async def invalidate(self) -> None:
        """Empty the session and carry what is left — nothing — to a new ID.

        The attributes are dropped and the entry under the old ID deleted,
        so nothing of the session survives but the session itself; the
        cookie is issued again under the new ID, never taken away.
        """
        await self.clear()
        await self.migrate(destroy_old=True)

    @override
    async def save(self) -> None:
        """Write the attributes through the storage.

        A session that was never started is left alone — there is nothing
        to write and no entry to make — so the listener that saves every
        response needs no condition of its own. A session that holds no
        attribute deletes the entry rather than writing an empty one: a
        request that only consumed its session leaves none behind.

        The entry is written to live as long as the cookie config's
        ``lifetime`` names, the application's notion of how long a session
        lives; a ``lifetime`` of ``None`` — the browser session, which
        names no moment to expire at — leaves the span to the storage's
        own default.

        Raises:
            SessionError: When the storage fails to write or to delete.
            InvalidArgumentError: When the storage keeps values in a format
                an attribute cannot round-trip — the cache-pool storage
                refuses one here, at the boundary, rather than losing it
                quietly.
        """
        if not self._started:
            return

        if not self._attributes:
            await self._storage.delete(self._id)
            return

        await self._storage.write(self._id, self._attributes, self._cookie.lifetime)

    @override
    def get_id(self) -> str:
        """Return the ID the session is known under, decided at construction."""
        return self._id

    @override
    def staged_set_cookie(self) -> str | None:
        """Return the ``Set-Cookie`` value that carries the ID, when it must be sent.

        The cookie is staged when the ID was made for this request — no
        readable one arrived — or was changed by ``migrate()`` or
        ``invalidate()``; a request that reattached the ID it was given
        sends nothing, so the client is not told a cookie it already has.
        The value is never the cleared form: ``invalidate()`` re-issues
        under the new ID, and nothing in this library takes a session
        cookie away.

        Returns:
            The header value, ready for the response's ``Set-Cookie``, or
            ``None`` when the ID the request arrived with still stands.
        """
        if not (self._id_generated or self._id_changed):
            return None

        expires = None
        if self._cookie.lifetime is not None:
            expires = datetime.now(UTC) + timedelta(seconds=self._cookie.lifetime)

        return cookie_header_value(
            self._cookie.name,
            self._id,
            expires=expires,
            path=self._cookie.path,
            domain=self._cookie.domain,
            secure=self._cookie.secure,
            httponly=self._cookie.httponly,
            samesite=self._cookie.samesite,
        )


def _is_session_id(value: str | None) -> TypeGuard[str]:
    """Tell whether ``value`` reads as a session ID this library reattaches.

    Uppercase hex is no ID here: the IDs this library makes are lowercase,
    and accepting an upper-case spelling would store one entry under two
    names.
    """
    return value is not None and _ID_PATTERN.fullmatch(value) is not None
