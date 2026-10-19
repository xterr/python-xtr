"""Remembering the OIDC provider sessions a back-channel logout ended."""

from __future__ import annotations

from hashlib import sha256
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from xtr_cache_contracts import CacheItemPoolInterface

__all__ = ["OidcEndedSessions"]


@final
class OidcEndedSessions:
    """Remembers the OIDC provider sessions a back-channel logout ended.

    A logout token names the provider session by its ``sid`` claim, and
    arrives outside of any request of the end-user: nothing of that browser
    is at hand, not even its session cookie, so the end is written down here
    and acted on when that browser comes back, by the back-channel logout
    listener.

    The pool has to be shared by every server of the application, as the
    logout token reaches any one of them, and the session it names was
    opened by another: an adapter local to one process, such as the array
    one, loses what the others recorded.
    """

    __slots__ = ("_cache", "_lifetime", "_namespace")

    def __init__(
        self,
        cache: CacheItemPoolInterface,
        namespace: str,
        lifetime: int,
    ) -> None:
        """Record where the ended sessions are kept, and for how long.

        Args:
            cache: The pool the ended sessions are remembered in. It has to
                be one every server of the application shares.
            namespace: The firewall the sessions belong to, so that two
                firewalls of one application, with two providers, never read
                each other's entries.
            lifetime: How long an ended session is remembered, in seconds,
                which has to be at least how long a session of this
                application can stay idle.
        """
        self._cache = cache
        self._namespace = namespace
        self._lifetime = lifetime

    async def record(self, sid: str) -> None:
        """Record that the given provider session has ended.

        The entry has to outlive the sessions that can present it: one
        dropped too early hands the browser back a working login, where one
        kept too long costs one opaque key in the pool.

        Recording the same end twice is what it already says, which is what
        makes replaying a logout token harmless.

        Args:
            sid: The ``sid`` claim of the logout token, naming the session
                at the provider.
        """
        item = await self._cache.get_item(self._key(sid))
        _ = item.set(True).expires_after(self._lifetime)
        _ = await self._cache.save(item)

    async def has(self, sid: str) -> bool:
        """Tell whether the given provider session is one a back-channel logout ended."""
        return await self._cache.has_item(self._key(sid))

    def _key(self, sid: str) -> str:
        """Return the key the ended session ``sid`` is remembered under.

        A ``sid`` is opaque and the cache contract reserves characters:
        hashed rather than escaped, which also keeps it out of the cache
        backend.
        """
        return f"oidc_ended_session.{self._namespace}.{sha256(sid.encode()).hexdigest()}"
