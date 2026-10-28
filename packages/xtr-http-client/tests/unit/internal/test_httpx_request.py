from __future__ import annotations

import io
import os
from typing import TYPE_CHECKING, BinaryIO, cast

import anyio.lowlevel
import httpx
import pytest
from xtr_http_message import Request

from xtr_http_client.exception import InvalidArgumentError, TransportError
from xtr_http_client.internal.httpx_request import (
    assemble_headers,
    assemble_payload,
    base_uri,
    checked_body,
    header_values,
    pin_host,
    target_url,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping, Sequence
    from pathlib import Path

pytestmark = pytest.mark.anyio


async def _pieces(*parts: bytes) -> AsyncIterator[bytes]:
    for part in parts:
        await anyio.lowlevel.checkpoint()
        yield part


def _opened_by_bytes(path: Path) -> BinaryIO:
    # A file opened by a bytes path carries its name as bytes, which is the subject here.
    return open(os.fsencode(path), "rb")  # noqa: PTH123 -- a Path cannot be opened by bytes


async def _not_bytes() -> AsyncIterator[bytes]:
    await anyio.lowlevel.checkpoint()
    yield cast("bytes", cast("object", ["not", "bytes"]))


# ── the URL a request is made to ────────────────────────────────────────────


def test_a_relative_uri_is_resolved_against_the_base() -> None:
    url = target_url(Request("GET", "../404"), {"base_uri": "http://example.test/abc/"})

    assert str(url) == "http://example.test/404"


def test_the_first_of_several_bases_is_the_one_a_single_attempt_resolves_against() -> None:
    assert base_uri(["http://first.test/", "http://second.test/"]) == "http://first.test/"


@pytest.mark.parametrize("base", [42, [], {}, [7]])
def test_a_base_that_is_not_a_url_is_refused(base: object) -> None:
    with pytest.raises(InvalidArgumentError, match='Option "base_uri"'):
        _ = base_uri(base)


def test_the_query_option_is_merged_into_the_one_the_uri_already_carried() -> None:
    url = target_url(Request("GET", "http://example.test/?a=a"), {"query": {"b": "b"}})

    assert str(url) == "http://example.test/?a=a&b=b"


def test_an_absolute_uri_ignores_the_base() -> None:
    url = target_url(Request("GET", "http://example.test/here"), {"base_uri": "http://other.test/"})

    assert str(url) == "http://example.test/here"


# ── the headers sent ────────────────────────────────────────────────────────


def test_the_host_a_request_worked_out_for_itself_is_not_sent() -> None:
    headers = assemble_headers(Request("GET", "http://example.test:8057/"), {})

    assert headers == []


def test_a_host_set_by_hand_is_sent_as_given() -> None:
    request = Request("GET", "http://example.test/", headers={"Host": "chosen.test"})

    assert assemble_headers(request, {}) == [("Host", "chosen.test")]


def test_a_header_the_request_carries_wins_and_one_it_lacks_is_filled_in() -> None:
    request = Request("GET", "http://example.test/", headers={"Foo": "from-request"})

    headers = assemble_headers(
        request,
        {"headers": {"foo": "from-options", "Bar": "from-options"}},
    )

    assert headers == [("Foo", "from-request"), ("Bar", "from-options")]


def test_a_header_given_several_values_sends_all_of_them() -> None:
    headers = assemble_headers(
        Request("GET", "/"),
        {"headers": {"Accept": ["text/html", "text/plain"]}},
    )

    assert headers == [("Accept", "text/html"), ("Accept", "text/plain")]


@pytest.mark.parametrize("value", [42, None])
def test_a_header_value_that_is_neither_text_nor_a_list_is_refused(value: object) -> None:
    with pytest.raises(InvalidArgumentError, match='Option "headers"'):
        _ = header_values("Accept", value)


def test_the_values_of_a_header_sequence_are_each_sent_as_text() -> None:
    assert header_values("X-Count", cast("Sequence[object]", [1, 2])) == [
        ("X-Count", "1"),
        ("X-Count", "2"),
    ]


def test_a_bearer_token_fills_an_authorization_the_request_has_none_of() -> None:
    headers = assemble_headers(Request("GET", "/"), {"auth_bearer": "a-token"})

    assert headers == [("Authorization", "Bearer a-token")]


def test_a_bearer_token_replaces_no_authorization_the_request_carries() -> None:
    request = Request("GET", "/", headers={"Authorization": "Bearer from-the-request"})

    headers = assemble_headers(request, {"auth_bearer": "from-the-option"})

    assert headers == [("Authorization", "Bearer from-the-request")]


# ── the body sent ───────────────────────────────────────────────────────────


async def test_a_request_body_is_what_is_sent_and_is_labelled_as_a_form() -> None:
    headers: list[tuple[str, str]] = []

    payload = await assemble_payload(Request("POST", "/", body=b"foo=bar"), {}, headers)

    assert payload.content == b"foo=bar"
    assert headers == [("Content-Type", "application/x-www-form-urlencoded")]


async def test_a_request_body_keeps_the_content_type_the_request_declared() -> None:
    request = Request("POST", "/", headers={"Content-Type": "text/plain"}, body=b"hello")
    headers = assemble_headers(request, {})

    payload = await assemble_payload(request, {}, headers)

    assert payload.content == b"hello"
    assert headers == [("Content-Type", "text/plain")]


@pytest.mark.parametrize("option", [{"body": {"foo": "baz"}}, {"json": {"foo": "baz"}}])
async def test_a_body_given_twice_is_refused_word_for_word(
    option: Mapping[str, object],
) -> None:
    request = Request("POST", "/", body=b"foo=bar")
    expected = (
        'Define either the request body or the "body" or "json" option, '
        "setting both is not supported."
    )

    with pytest.raises(InvalidArgumentError) as refusal:
        _ = await assemble_payload(request, option, [])

    assert str(refusal.value) == expected


async def test_a_json_option_is_sent_as_a_document() -> None:
    payload = await assemble_payload(Request("POST", "/"), {"json": {"foo": "bar"}}, [])

    assert payload.document == {"foo": "bar"}
    assert payload.content is None


async def test_a_mapping_body_is_sent_as_a_form_the_backend_encodes() -> None:
    headers: list[tuple[str, str]] = []

    payload = await assemble_payload(Request("POST", "/"), {"body": {"foo": "bar"}}, headers)

    assert payload.form == {"foo": "bar"}
    assert payload.files is None
    assert headers == []


async def test_a_mapping_holding_a_file_sends_the_file_apart_from_the_plain_values(
    tmp_path: Path,
) -> None:
    photo = tmp_path / "photo.png"
    _ = photo.write_bytes(b"\x89PNG")
    headers: list[tuple[str, str]] = []

    with photo.open("rb") as file:
        payload = await assemble_payload(
            Request("POST", "/"), {"body": {"caption": "hello", "photo": file}}, headers
        )

        assert payload.form == {"caption": "hello"}
        assert payload.files == {"photo": ("photo.png", file, "image/png")}
    assert headers == []


async def test_a_file_opened_by_a_bytes_path_is_named_after_its_last_part(
    tmp_path: Path,
) -> None:
    notes = tmp_path / "notes.txt"
    _ = notes.write_bytes(b"hello")

    with _opened_by_bytes(notes) as file:
        payload = await assemble_payload(Request("POST", "/"), {"body": {"notes": file}}, [])

        assert payload.files == {"notes": ("notes.txt", file, "text/plain")}


async def test_a_file_with_no_name_goes_as_unknown_of_no_guessable_type() -> None:
    file = io.BytesIO(b"plain bytes")

    payload = await assemble_payload(Request("POST", "/"), {"body": {"data": file}}, [])

    assert payload.form == {}
    assert payload.files == {"data": ("unknown", file, "application/octet-stream")}


@pytest.mark.parametrize(
    ("value", "given"),
    [({"a": 1}, "dict"), ([{"a": 1}], "list"), ((1, [2]), "tuple"), (object(), "object")],
)
async def test_a_multipart_body_refuses_a_value_no_part_can_hold(value: object, given: str) -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = await assemble_payload(
            Request("POST", "/"), {"body": {"m": value, "data": io.BytesIO(b"x")}}, []
        )

    assert str(raised.value) == (
        'Option "body" field "m" must be a string, a number, a boolean, None or a list of '
        f'them when the body is multipart, "{given}" given.'
    )


async def test_a_multipart_body_takes_scalars_and_lists_of_them() -> None:
    form: dict[str, object] = {"s": "x", "b": b"y", "n": 1, "f": 1.5, "t": True, "z": None}
    form["l"] = ["a", 1, None]

    payload = await assemble_payload(
        Request("POST", "/"), {"body": {**form, "data": io.BytesIO(b"x")}}, []
    )

    assert payload.form == form


async def test_a_url_encoded_body_keeps_its_values_as_given() -> None:
    payload = await assemble_payload(Request("POST", "/"), {"body": {"m": {"a": 1}}}, [])

    assert payload.form == {"m": {"a": 1}}


async def test_a_multipart_content_type_naming_its_boundary_is_kept() -> None:
    headers = [("Content-Type", "multipart/form-data; boundary=xtr-boundary")]

    _ = await assemble_payload(Request("POST", "/"), {"body": {"data": io.BytesIO(b"x")}}, headers)

    assert headers == [("Content-Type", "multipart/form-data; boundary=xtr-boundary")]


@pytest.mark.parametrize(
    "content_type",
    ["multipart/form-data", "application/json", "Multipart/Form-Data; boundary=b1"],
)
async def test_a_content_type_naming_no_usable_boundary_is_left_for_the_backend_to_set(
    content_type: str,
) -> None:
    headers = [("Content-Type", content_type), ("Accept", "*/*")]

    _ = await assemble_payload(Request("POST", "/"), {"body": {"data": io.BytesIO(b"x")}}, headers)

    assert headers == [("Accept", "*/*")]


async def test_a_text_body_is_sent_as_it_is() -> None:
    headers: list[tuple[str, str]] = []

    payload = await assemble_payload(Request("POST", "/"), {"body": "foo=bar"}, headers)

    assert payload.content == "foo=bar"
    assert headers == [("Content-Type", "application/x-www-form-urlencoded")]


async def test_a_body_produced_in_pieces_is_sent_as_it_is_produced() -> None:
    headers: list[tuple[str, str]] = []

    payload = await assemble_payload(Request("POST", "/"), {"body": _pieces(b"foo=bar")}, headers)

    assert payload.content is not None
    assert headers == [("Content-Type", "application/x-www-form-urlencoded")]


@pytest.mark.parametrize("body", [b"", "", 42])
async def test_a_body_with_nothing_in_it_sends_nothing(body: object) -> None:
    payload = await assemble_payload(Request("POST", "/"), {"body": body}, [])

    assert payload == (None, None, None, None)


async def test_a_body_producing_anything_other_than_bytes_fails_the_request() -> None:
    pieces = checked_body(_not_bytes())

    with pytest.raises(TransportError, match="which is not bytes"):
        _ = await anext(pieces)


# ── the address a host is pinned to ─────────────────────────────────────────


def test_a_pinned_host_is_reached_at_its_address_and_still_named_in_the_headers() -> None:
    headers = [("Host", "stale.test")]

    url, extensions = pin_host(
        httpx.URL("http://pinned.example:8057/"),
        {"resolve": {"pinned.example": "127.0.0.1"}},
        {},
        headers,
    )

    assert str(url) == "http://127.0.0.1:8057/"
    assert headers == [("Host", "pinned.example:8057")]
    assert extensions == {"sni_hostname": "pinned.example"}


def test_a_pinned_host_on_a_standard_port_is_named_without_one() -> None:
    headers: list[tuple[str, str]] = []

    _, _ = pin_host(
        httpx.URL("http://pinned.example/"),
        {"resolve": {"pinned.example": "127.0.0.1"}},
        {},
        headers,
    )

    assert headers == [("Host", "pinned.example")]


def test_a_host_pinned_once_stays_pinned_for_the_pool() -> None:
    remembered: dict[str, str] = {}

    _ = pin_host(
        httpx.URL("http://pinned.example/"),
        {"resolve": {"pinned.example": "127.0.0.1"}},
        remembered,
        [],
    )
    url, extensions = pin_host(httpx.URL("http://pinned.example/"), {}, remembered, [])

    assert str(url) == "http://127.0.0.1/"
    assert extensions == {"sni_hostname": "pinned.example"}


def test_a_host_nobody_pinned_is_left_to_a_resolver() -> None:
    headers: list[tuple[str, str]] = []

    url, extensions = pin_host(httpx.URL("http://example.test/"), {}, {}, headers)

    assert str(url) == "http://example.test/"
    assert extensions == {}
    assert headers == []
