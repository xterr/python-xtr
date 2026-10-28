"""The session a stateful request carries."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from xtr_http_message import ServerRequest

if TYPE_CHECKING:
    from collections.abc import Mapping

from xtr_http_foundation import Session, SessionCookieConfig
from xtr_http_foundation.response_cookie import cookie_header_value

_ID = "0123456789abcdef" * 3
_OTHER_ID = "fedcba9876543210" * 3


@final
class SpyStorage:
    """A storage that counts the calls it is asked for, answering from a dict.

    The counts are the proof that a session touches nothing but the calls it
    means to make: construction reads nothing, the members that cannot reach
    the storage read nothing, and the first attribute reads exactly once.
    """

    __slots__ = ("deletes", "read_ids", "reads", "stored", "writes", "written_ttls")

    def __init__(self, stored: dict[str, dict[str, object]] | None = None) -> None:
        self.stored: dict[str, dict[str, object]] = dict(stored or {})
        self.reads = 0
        self.writes = 0
        self.deletes = 0
        self.read_ids: list[str] = []
        self.written_ttls: list[float | None] = []

    async def read(self, session_id: str) -> Mapping[str, object] | None:
        self.reads += 1
        self.read_ids.append(session_id)
        return self.stored.get(session_id)

    async def write(self, session_id: str, data: Mapping[str, object], ttl: float | None) -> None:
        self.writes += 1
        self.written_ttls.append(ttl)
        self.stored[session_id] = dict(data)

    async def delete(self, session_id: str) -> None:
        self.deletes += 1
        _ = self.stored.pop(session_id, None)


@pytest.mark.anyio
async def test_it_reads_nothing_before_the_first_attribute_is_asked_for() -> None:
    storage = SpyStorage()
    session = Session(storage)

    assert session.get_id()
    assert session.is_started() is False
    assert session.staged_set_cookie()

    assert storage.reads == 0

    assert await session.get("theme") is None

    assert storage.reads == 1


@pytest.mark.anyio
async def test_it_starts_once_for_a_whole_request() -> None:
    storage = SpyStorage()
    session = Session(storage)

    assert await session.get("theme") is None
    await session.set("visits", 1)

    assert await session.has("visits")

    assert storage.reads == 1


@pytest.mark.anyio
async def test_it_loads_the_attributes_the_storage_holds_under_the_id() -> None:
    session = Session(SpyStorage(stored={_ID: {"theme": "dark"}}), cookie_value=_ID)

    assert await session.get("theme") == "dark"


@pytest.mark.anyio
async def test_it_answers_the_default_for_an_attribute_it_does_not_hold() -> None:
    session = Session(SpyStorage())

    assert await session.get("theme", "light") == "light"


@pytest.mark.anyio
async def test_it_holds_an_attribute_it_was_given() -> None:
    session = Session(SpyStorage())

    await session.set("user", "alice")

    assert await session.get("user") == "alice"


@pytest.mark.anyio
async def test_it_tells_whether_an_attribute_is_there() -> None:
    session = Session(SpyStorage())
    await session.set("user", "alice")

    assert await session.has("user") is True
    assert await session.has("theme") is False


@pytest.mark.anyio
async def test_it_removes_an_attribute_and_returns_what_it_held() -> None:
    session = Session(SpyStorage())
    await session.set("user", "alice")

    assert await session.remove("user") == "alice"
    assert await session.has("user") is False


@pytest.mark.anyio
async def test_it_removes_an_attribute_that_was_never_there() -> None:
    session = Session(SpyStorage())

    assert await session.remove("user") is None


@pytest.mark.anyio
async def test_it_clears_every_attribute() -> None:
    session = Session(SpyStorage())
    await session.set("user", "alice")
    await session.set("theme", "dark")

    await session.clear()

    assert await session.has("user") is False
    assert await session.has("theme") is False


@pytest.mark.anyio
async def test_it_migrates_to_a_new_id_keeping_the_attributes() -> None:
    session = Session(SpyStorage(), cookie_value=_ID)
    await session.set("user", "alice")
    old_id = session.get_id()

    await session.migrate()

    assert session.get_id() != old_id
    assert await session.get("user") == "alice"
    assert session.staged_set_cookie() is not None


@pytest.mark.anyio
async def test_it_keeps_the_old_entry_unless_the_migrate_is_asked_to_destroy_it() -> None:
    storage = SpyStorage(stored={_ID: {"theme": "dark"}})

    keeper = Session(storage, cookie_value=_ID)
    await keeper.migrate()

    assert storage.deletes == 0
    assert storage.stored == {_ID: {"theme": "dark"}}

    destroyer = Session(storage, cookie_value=_ID)
    await destroyer.migrate(destroy_old=True)

    assert storage.deletes == 1
    assert storage.stored == {}


@pytest.mark.anyio
async def test_it_invalidates_by_emptying_the_attributes_and_destroying_the_old_entry() -> None:
    storage = SpyStorage(stored={_ID: {"theme": "dark"}})
    session = Session(storage, cookie_value=_ID)
    await session.set("user", "alice")
    old_id = session.get_id()

    await session.invalidate()

    assert await session.get("user") is None
    assert session.get_id() != old_id
    assert storage.deletes == 1
    assert storage.stored == {}
    assert session.staged_set_cookie() is not None


@pytest.mark.anyio
async def test_it_treats_an_unreadable_id_cookie_as_no_cookie_at_all() -> None:
    storage = SpyStorage()
    session = Session(storage, cookie_value="not-a-session-id")

    assert session.get_id() != "not-a-session-id"
    assert session.staged_set_cookie() is not None

    assert await session.get("theme") is None

    assert "not-a-session-id" not in storage.read_ids


@pytest.mark.anyio
async def test_it_reattaches_the_id_the_cookie_carried() -> None:
    session = Session(SpyStorage(), cookie_value=_ID)

    assert session.get_id() == _ID
    assert session.staged_set_cookie() is None


@pytest.mark.anyio
async def test_it_saves_the_attributes_through_the_storage() -> None:
    storage = SpyStorage()
    session = Session(storage)
    await session.set("theme", "dark")

    await session.save()

    assert storage.writes == 1
    assert storage.stored == {session.get_id(): {"theme": "dark"}}
    assert storage.written_ttls == [None]


@pytest.mark.anyio
async def test_it_saves_nothing_for_a_session_that_never_started() -> None:
    storage = SpyStorage()
    session = Session(storage)

    await session.save()

    assert storage.writes == 0
    assert storage.deletes == 0


@pytest.mark.anyio
async def test_it_deletes_the_entry_when_a_started_session_saves_empty() -> None:
    storage = SpyStorage(stored={_ID: {"theme": "dark"}})
    session = Session(storage, cookie_value=_ID)

    assert await session.get("theme") == "dark"
    await session.clear()
    await session.save()

    assert storage.writes == 0
    assert storage.deletes == 1
    assert storage.stored == {}


@pytest.mark.anyio
async def test_it_writes_the_entry_to_live_as_long_as_the_cookie_config_names() -> None:
    storage = SpyStorage()
    session = Session(storage, cookie=SessionCookieConfig(lifetime=3600))
    await session.set("theme", "dark")

    await session.save()

    assert storage.written_ttls == [3600]


def test_it_stages_the_cookie_the_builder_writes_for_a_made_id() -> None:
    session = Session(SpyStorage())

    assert session.staged_set_cookie() == cookie_header_value("xtr_session", session.get_id())


def test_it_stages_the_cookie_dated_by_the_lifetime() -> None:
    session = Session(SpyStorage(), cookie=SessionCookieConfig(lifetime=3600))

    staged = session.staged_set_cookie()

    assert staged is not None
    assert "expires=" in staged
    assert "Max-Age=" in staged


@pytest.mark.anyio
async def test_it_leaves_the_old_id_reading_as_nothing_after_a_destroying_migrate() -> None:
    storage = SpyStorage()
    session = Session(storage, cookie_value=_ID)
    await session.set("user", "alice")
    await session.save()

    assert storage.stored == {_ID: {"user": "alice"}}

    await session.migrate(destroy_old=True)
    await session.save()

    assert await Session(storage, cookie_value=_ID).get("user") is None
    assert await Session(storage, cookie_value=session.get_id()).get("user") == "alice"


@pytest.mark.anyio
async def test_it_keeps_the_attributes_just_stored_when_the_id_is_rotated() -> None:
    storage = SpyStorage()
    session = Session(storage, cookie_value=_ID)
    await session.set("user", "alice")

    await session.migrate(destroy_old=True)
    await session.save()

    assert await session.get("user") == "alice"
    assert await Session(storage, cookie_value=session.get_id()).get("user") == "alice"


@pytest.mark.anyio
async def test_it_never_mixes_two_sessions_over_one_storage() -> None:
    storage = SpyStorage()
    first = Session(storage, cookie_value=_ID)
    second = Session(storage, cookie_value=_OTHER_ID)
    await first.set("user", "alice")
    await second.set("user", "bob")

    await first.save()
    await second.save()

    assert await Session(storage, cookie_value=_ID).get("user") == "alice"
    assert await Session(storage, cookie_value=_OTHER_ID).get("user") == "bob"


def test_it_builds_the_session_from_the_id_cookie_the_request_carried() -> None:
    request = ServerRequest("GET", "/").with_cookie_params({"xtr_session": _ID})

    session = Session.from_request(request, SpyStorage())

    assert session.get_id() == _ID
    assert session.staged_set_cookie() is None


def test_it_reads_the_cookie_the_config_names() -> None:
    request = ServerRequest("GET", "/").with_cookie_params({"app_session": _ID})
    cookie = SessionCookieConfig(name="app_session")

    session = Session.from_request(request, SpyStorage(), cookie=cookie)

    assert session.get_id() == _ID


def test_it_treats_a_request_without_the_cookie_as_a_new_session() -> None:
    session = Session.from_request(ServerRequest("GET", "/"), SpyStorage())

    assert session.staged_set_cookie() is not None
    assert session.get_id() != _ID
