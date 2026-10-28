"""An upload's other fields, as the bot API reads them from a multipart body."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import TYPE_CHECKING, cast

import httpx
import pytest
from xtr_http_client import JsonMockResponse, MockHttpClient
from xtr_notifier.message import ChatMessage

from xtr_telegram_notifier import TelegramOptions, TelegramTransport
from xtr_telegram_notifier.reply.markup import InlineKeyboardMarkup
from xtr_telegram_notifier.reply.markup.button import InlineKeyboardButton

if TYPE_CHECKING:
    from xtr_http_client import MockResponse
    from xtr_http_client_contracts import RequestOptions

FIXTURE_FILE = str(Path(__file__).parents[1] / "fixtures" / "image.png")
_MARKUP = InlineKeyboardMarkup().inline_keyboard(
    [InlineKeyboardButton("Open").url("https://example.com")]
)
_MARKUP_JSON = json.dumps(_MARKUP.to_array())


_Upload = tuple[dict[str, object], tuple[str, bytes, str]]


async def _uploaded_body(options: TelegramOptions) -> _Upload:
    """Send ``options`` with a photo upload; return the other fields and the photo's part."""
    seen: list[_Upload] = []

    def answer(_verb: str, _url: str, request: RequestOptions) -> MockResponse:
        body = request.get("body")
        assert isinstance(body, dict)
        fields: dict[str, object] = dict(body)
        upload = fields.pop("photo")
        assert isinstance(upload, io.BufferedReader)
        seen.append((fields, (Path(upload.name).name, upload.read(), "image/png")))
        return JsonMockResponse({"ok": True, "result": {"message_id": 1}})

    transport = TelegramTransport("1:T", "42", MockHttpClient(answer))
    _ = await transport.send(ChatMessage("Hi", options.to_options()))
    [upload] = seen
    return upload


@pytest.mark.anyio
async def test_a_nested_option_beside_an_upload_is_sent_as_json_text() -> None:
    body, _ = await _uploaded_body(
        TelegramOptions().upload_photo(FIXTURE_FILE).reply_markup(_MARKUP).has_spoiler(True)
    )

    assert body["reply_markup"] == _MARKUP_JSON
    assert body["has_spoiler"] is True
    assert body["chat_id"] == "42"


@pytest.mark.anyio
async def test_the_upload_body_encodes_as_multipart_with_the_markup_as_json() -> None:
    body, photo = await _uploaded_body(
        TelegramOptions().upload_photo(FIXTURE_FILE).reply_markup(_MARKUP).has_spoiler(True)
    )

    encoded = httpx.Request("POST", "https://example.com", data=body, files={"photo": photo}).read()

    assert b'name="reply_markup"\r\n\r\n' + _MARKUP_JSON.encode() + b"\r\n" in encoded
    assert b'name="has_spoiler"\r\n\r\ntrue\r\n' in encoded
    assert b'name="photo"; filename="image.png"' in encoded


@pytest.mark.anyio
async def test_a_message_without_an_upload_keeps_its_markup_as_json_data() -> None:
    seen: list[object] = []

    def answer(_verb: str, _url: str, request: RequestOptions) -> MockResponse:
        body = request.get("json")
        assert isinstance(body, dict)
        seen.append(cast("dict[str, object]", body)["reply_markup"])
        return JsonMockResponse({"ok": True, "result": {"message_id": 1}})

    transport = TelegramTransport("1:T", "42", MockHttpClient(answer))
    _ = await transport.send(
        ChatMessage("Hi", TelegramOptions().reply_markup(_MARKUP).to_options())
    )

    assert seen == [_MARKUP.to_array()]
