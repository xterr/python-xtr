"""Tests for the connected side of :class:`xtr_http_message.server_request.ServerRequest`."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest

from xtr_http_message import LazyStream, ServerRequest
from xtr_http_message.exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Mapping

pytestmark = pytest.mark.anyio


@final
class _Source:
    """A request source a test drives by hand.

    What materialisation yields is set on it up front; the peeks answer it
    only once materialisation has run, the way a connection's do.
    """

    __slots__ = ("body", "calls", "files", "parsed", "path_params")

    def __init__(
        self,
        body: bytes = b"",
        parsed: object | None = None,
        files: Mapping[str, object] | None = None,
    ) -> None:
        self.body = body
        self.parsed = parsed
        self.files: Mapping[str, object] = {} if files is None else files
        self.path_params: dict[str, object] = {}
        self.calls = 0

    async def materialise(self) -> bytes:
        self.calls += 1
        return self.body

    def parsed_body(self) -> object | None:
        return self.parsed if self.calls else None

    def uploaded_files(self) -> Mapping[str, object]:
        return self.files if self.calls else {}

    def attributes(self) -> Mapping[str, object]:
        return self.path_params


def _over(source: _Source) -> ServerRequest:
    """Return a request born connected over ``source``, with a head to match."""
    return ServerRequest.over(
        "POST",
        "https://bookshop.test/books/978-0141439518?quantity=2",
        source=source,
        headers={"host": "bookshop.test", "content-type": "application/json"},
        server_params={"method": "POST"},
        cookies={"session": "abc"},
        query={"quantity": "2"},
        protocol_version="1.1",
    )


def test_the_head_is_what_was_passed_eagerly() -> None:
    served = _over(_Source())

    assert (served.get_method(), served.get_protocol_version()) == ("POST", "1.1")
    assert served.get_uri().get_path() == "/books/978-0141439518"
    assert served.get_request_target() == "/books/978-0141439518?quantity=2"
    assert dict(served.get_headers()) == {
        "host": ["bookshop.test"],
        "content-type": ["application/json"],
    }
    assert served.get_cookie_params() == {"session": "abc"}
    assert served.get_query_params() == {"quantity": "2"}
    assert served.get_server_params() == {"method": "POST"}


def test_a_header_the_message_grammar_refuses_is_left_out() -> None:
    served = ServerRequest.over(
        "GET",
        "/",
        source=_Source(),
        headers={"host": "a.test", " x-broken": "abc"},
    )

    assert (served.has_header(" x-broken"), served.has_header("x-broken")) == (False, False)


def test_a_body_cannot_be_given_alongside_a_source() -> None:
    with pytest.raises(InvalidArgumentError) as refusal:
        _ = ServerRequest.over("GET", "/", source=_Source(), body=b"both")

    assert "body=" in str(refusal.value)
    assert "source" in str(refusal.value)


def test_the_body_is_read_only_when_something_reads_the_stream() -> None:
    source = _Source(body=b"four words")
    served = _over(source)

    assert (source.calls, served.get_parsed_body(), served.get_uploaded_files()) == (0, None, {})

    body = served.get_body()

    assert isinstance(body, LazyStream)
    assert source.calls == 0
    assert served.get_body() is body


async def test_the_first_read_materialises_the_body_once() -> None:
    source = _Source(body=b"four words", parsed={"title": "dune"}, files={"doc": object()})
    served = _over(source)

    assert await served.get_body().get_contents() == b"four words"

    assert source.calls == 1
    assert served.get_parsed_body() == {"title": "dune"}
    assert set(served.get_uploaded_files()) == {"doc"}
    # The buffer serves every later read, and rewinds.
    assert await served.get_body().get_contents() == b"four words"


async def test_the_parsed_side_answers_what_materialisation_yields() -> None:
    source = _Source(body=b"[1, 2]", parsed=None)
    served = _over(source)

    assert served.get_parsed_body() is None
    assert await served.get_body().get_contents() == b"[1, 2]"
    assert served.get_parsed_body() is None


def test_the_attributes_are_live_off_the_source() -> None:
    source = _Source()
    served = _over(source)

    assert served.get_attributes() == {}
    assert served.get_attribute("isbn", "none") == "none"

    source.path_params["isbn"] = "978-0141439518"

    assert served.get_attributes() == {"isbn": "978-0141439518"}
    assert served.get_attribute("isbn") == "978-0141439518"


async def test_ensure_parsed_materialises_a_body_nobody_has_read() -> None:
    source = _Source(body=b'{"title": "dune"}', parsed={"title": "dune"})
    served = _over(source)

    await served.ensure_parsed()

    assert (source.calls, served.get_parsed_body()) == (1, {"title": "dune"})


async def test_ensure_parsed_is_a_no_op_once_the_body_has_been_read() -> None:
    source = _Source(body=b'{"title": "dune"}', parsed={"title": "dune"})
    served = _over(source)

    assert await served.get_body().get_contents() == b'{"title": "dune"}'
    await served.ensure_parsed()

    assert source.calls == 1


async def test_ensure_parsed_is_a_no_op_for_an_eager_request() -> None:
    request = ServerRequest("GET", "/")

    await request.ensure_parsed()

    assert await request.get_body().get_contents() == b""


async def test_the_with_members_detach_to_plain_eager_copies() -> None:
    source = _Source(body=b"kept")
    source.path_params["user"] = "ada"
    served = _over(source)

    copy = served.with_attribute("trace", "1").with_added_header("x-trace", "1")

    assert type(copy) is ServerRequest
    assert copy.get_attribute("user") == "ada"
    assert copy.get_attribute("trace") == "1"
    assert copy.get_header_line("x-trace") == "1"
    # The parsed side is the peek at the moment of the copy: nothing has been
    # read, so nothing has been parsed.
    assert copy.get_parsed_body() is None
    # The view is left as it was: no attribute, no header, nothing read.
    assert served.get_attribute("user") == "ada"
    assert served.get_attribute("trace") is None
    assert served.get_header_line("x-trace") == ""
    assert source.calls == 0


async def test_a_copy_made_after_a_read_carries_what_the_read_parsed() -> None:
    source = _Source(body=b'{"title": "dune"}', parsed={"title": "dune"})
    served = _over(source)

    assert await served.get_body().get_contents() == b'{"title": "dune"}'

    copy = served.with_method("PUT")

    assert copy.get_parsed_body() == {"title": "dune"}


async def test_a_detached_copy_shares_the_one_stream_and_never_reads_the_source() -> None:
    source = _Source(body=b"kept")
    served = _over(source)

    copy = served.with_method("PUT")

    assert copy.get_body() is served.get_body()
    assert await copy.get_body().get_contents() == b"kept"

    assert source.calls == 1


async def test_a_detached_copy_freezes_the_attributes_as_they_are() -> None:
    source = _Source()
    served = _over(source)

    copy = served.with_method("PUT")
    source.path_params["isbn"] = "978-0141439518"

    assert copy.get_attributes() == {}
    assert served.get_attributes() == {"isbn": "978-0141439518"}


def test_without_attribute_removes_a_live_attribute_and_detaches() -> None:
    source = _Source()
    source.path_params["isbn"] = "978-0141439518"
    served = _over(source)

    without = served.without_attribute("isbn")

    assert type(without) is ServerRequest
    assert without.get_attributes() == {}
    assert served.get_attributes() == {"isbn": "978-0141439518"}


def test_without_attribute_on_a_connected_request_without_the_name_detaches() -> None:
    source = _Source()
    served = _over(source)

    without = served.without_attribute("isbn")

    assert type(without) is ServerRequest
    assert without is not served


def test_a_no_op_with_member_on_a_connected_request_detaches_too() -> None:
    source = _Source()
    served = _over(source)

    same_uri = served.with_uri(served.get_uri())
    same_version = served.with_protocol_version(served.get_protocol_version())
    without_header = served.without_header("x-absent")

    assert type(same_uri) is ServerRequest
    assert type(same_version) is ServerRequest
    assert type(without_header) is ServerRequest
    assert source.path_params == {}
