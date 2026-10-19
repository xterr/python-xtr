"""Refusing a token whose provider session a back-channel logout ended."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, final

import pytest
from xtr_cache import ArrayAdapter
from xtr_clock import MockClock
from xtr_security_core.authentication.token.null_token import NullToken
from xtr_security_core.user.in_memory_user import InMemoryUser

from xtr_security_http.authenticator.token.post_authentication_token import PostAuthenticationToken
from xtr_security_http.event.check_refreshed_user_event import CheckRefreshedUserEvent
from xtr_security_http.event_listener.oidc_back_channel_logout_listener import (
    OidcBackChannelLogoutListener,
)
from xtr_security_http.exception import OidcSessionEndedError
from xtr_security_http.oidc.oidc_ended_sessions import OidcEndedSessions

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from xtr_cache_contracts import ItemInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface

pytestmark = pytest.mark.anyio

_NOW = 1_000_000
_FROZEN = datetime.fromtimestamp(_NOW, tz=UTC)


@final
class _CountingPool:
    """An array pool that counts the lookups it was asked for."""

    def __init__(self) -> None:
        self._inner = ArrayAdapter(clock=MockClock(_FROZEN))
        self.lookups = 0

    async def get_items(self, keys: Iterable[str], /) -> Mapping[str, ItemInterface]:
        """Hand the items the inner pool does."""
        return await self._inner.get_items(keys)

    async def get_item(self, key: str, /) -> ItemInterface:
        """Hand the item the inner pool does."""
        return await self._inner.get_item(key)

    async def clear(self, prefix: str = "") -> bool:
        """Clear what the inner pool clears."""
        return await self._inner.clear(prefix)

    async def delete_item(self, key: str, /) -> bool:
        """Remove what the inner pool removes."""
        return await self._inner.delete_item(key)

    async def delete_items(self, keys: Iterable[str], /) -> bool:
        """Remove what the inner pool removes."""
        return await self._inner.delete_items(keys)

    async def has_item(self, key: str, /) -> bool:
        """Count the lookup, then answer it."""
        self.lookups += 1
        return await self._inner.has_item(key)

    async def save(self, item: ItemInterface, /) -> bool:
        """Store the item the inner pool does."""
        return await self._inner.save(item)

    async def save_deferred(self, item: ItemInterface, /) -> bool:
        """Queue the item the inner pool queues."""
        return await self._inner.save_deferred(item)

    async def commit(self) -> bool:
        """Commit what the inner pool commits."""
        return await self._inner.commit()


def _user() -> InMemoryUser:
    return InMemoryUser("alice", roles=["ROLE_USER"])


def _token(firewall: str = "main", **attributes: object) -> PostAuthenticationToken:
    token = PostAuthenticationToken(_user(), firewall, ["ROLE_USER"])
    for name, value in attributes.items():
        token.set_attribute(name, value)
    return token


def _event(token: TokenInterface) -> CheckRefreshedUserEvent:
    """A refreshed-user check over ``token``, seeded with an unchanged user."""
    user = _user()
    return CheckRefreshedUserEvent(token, user, user)


def _listener(pool: _CountingPool, firewall: str = "main") -> OidcBackChannelLogoutListener:
    return OidcBackChannelLogoutListener(OidcEndedSessions(pool, firewall, 3600), firewall)


def test_it_is_a_plain_callable_the_wiring_registers_itself() -> None:
    """No subscriber declaration: the wiring places it on the dispatcher it belongs on."""
    assert not hasattr(OidcBackChannelLogoutListener, "get_subscribed_events")


async def test_a_token_of_the_firewall_whose_session_ended_is_deauthenticated() -> None:
    pool = _CountingPool()
    await OidcEndedSessions(pool, "main", 3600).record("sid-1")
    listener = _listener(pool)
    event = _event(_token(oidc_sid="sid-1"))

    await listener(event)

    assert event.is_user_changed()
    exception = event.get_exception()
    assert isinstance(exception, OidcSessionEndedError)
    assert exception.message_key == "The OIDC provider ended the session this login belongs to."


async def test_a_token_minted_on_another_firewall_is_left_alone() -> None:
    pool = _CountingPool()
    listener = _listener(pool)
    event = _event(_token(firewall="api", oidc_sid="sid-1"))

    await listener(event)

    assert not event.is_user_changed()

    assert event.get_exception() is None
    assert pool.lookups == 0


async def test_a_token_of_a_kind_without_a_firewall_name_is_left_alone() -> None:
    pool = _CountingPool()
    listener = _listener(pool)
    event = _event(NullToken())

    await listener(event)

    assert not event.is_user_changed()
    assert pool.lookups == 0


async def test_a_token_naming_no_provider_session_is_left_alone() -> None:
    pool = _CountingPool()
    listener = _listener(pool)
    event = _event(_token())

    await listener(event)

    assert not event.is_user_changed()
    assert pool.lookups == 0


async def test_a_token_with_an_empty_sid_is_left_alone() -> None:
    pool = _CountingPool()
    listener = _listener(pool)
    event = _event(_token(oidc_sid=""))

    await listener(event)

    assert not event.is_user_changed()
    assert pool.lookups == 0


async def test_a_token_with_a_non_string_sid_is_left_alone() -> None:
    pool = _CountingPool()
    listener = _listener(pool)
    event = _event(_token(oidc_sid=7))

    await listener(event)

    assert not event.is_user_changed()
    assert pool.lookups == 0


async def test_a_session_the_logout_did_not_end_is_left_alone() -> None:
    pool = _CountingPool()
    listener = _listener(pool)
    event = _event(_token(oidc_sid="sid-1"))

    await listener(event)

    assert not event.is_user_changed()
    assert pool.lookups == 1


async def test_the_sid_is_matched_within_the_firewall_namespace() -> None:
    """Two providers minting the same opaque sid for two firewalls stay apart."""
    pool = _CountingPool()
    await OidcEndedSessions(pool, "api", 3600).record("sid-1")
    listener = _listener(pool, firewall="main")
    event = _event(_token(oidc_sid="sid-1"))

    await listener(event)

    assert not event.is_user_changed()
