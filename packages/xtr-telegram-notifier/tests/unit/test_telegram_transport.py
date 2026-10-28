from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from io import BufferedReader
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest
from xtr_http_client import JsonMockResponse, MockHttpClient, MockResponse
from xtr_notifier.exception import (
    LogicError,
    MultipleExclusiveOptionsUsedError,
    TransportError,
)
from xtr_notifier.message import ChatMessage, MessageOptions, PushMessage, SmsMessage
from xtr_notifier.testing import TransportCases, assert_transport_cases

from xtr_telegram_notifier import TelegramOptions, TelegramTransport
from xtr_telegram_notifier.reply.markup import InlineKeyboardMarkup
from xtr_telegram_notifier.reply.markup.button import InlineKeyboardButton

if TYPE_CHECKING:
    from xtr_http_client_contracts import RequestOptions

FIXTURE_FILE = str(Path(__file__).parents[1] / "fixtures" / "image.png")

FileCase = tuple[TelegramOptions, str, Sequence[tuple[str, object]]]


def _transport(
    client: MockHttpClient | None = None, channel: str | None = None, ssl: bool = True
) -> TelegramTransport:
    transport = TelegramTransport("token", channel, client or MockHttpClient())
    return transport.set_ssl(ssl)


def _sent(message_id: int = 1, **result: object) -> JsonMockResponse:
    return JsonMockResponse({"ok": True, "result": {"message_id": message_id, **result}})


def _expecting(endpoint: str, json: Mapping[str, object]) -> MockHttpClient:
    def answer(method: str, url: str, options: RequestOptions) -> MockResponse:
        assert method == "POST"
        assert url == f"https://api.telegram.org/bottoken/{endpoint}"
        assert options.get("json") == json
        return _sent()

    return MockHttpClient(answer)


def _never_called() -> MockHttpClient:
    def answer(_method: str, _url: str, _options: RequestOptions) -> MockResponse:
        pytest.fail("Telegram API should not be called")

    return MockHttpClient(answer)


@pytest.mark.anyio
async def test_it_does_what_every_transport_owes() -> None:
    await assert_transport_cases(
        TransportCases(
            create_transport=_transport,
            to_string=[
                ("telegram://api.telegram.org", _transport()),
                (
                    "telegram://api.telegram.org?channel=testChannel",
                    _transport(None, "testChannel"),
                ),
                ("telegram://api.telegram.org?ssl=false", _transport(None, None, False)),
                (
                    "telegram://api.telegram.org?channel=testChannel&ssl=false",
                    _transport(None, "testChannel", False),
                ),
            ],
            supported=[
                ChatMessage("Hello!"),
                ChatMessage("Hello!", TelegramOptions().to_options()),
            ],
            unsupported=[SmsMessage("0611223344", "Hello!"), PushMessage("Hello!", "")],
        )
    )


def test_it_refuses_a_chat_message_carrying_another_providers_options() -> None:
    assert not _transport().supports(ChatMessage("Hello!", MessageOptions("slack")))


def test_its_string_form_never_shows_the_token() -> None:
    transport = TelegramTransport("123:SECRET", "testChannel", MockHttpClient())

    assert "SECRET" not in str(transport)
    assert "SECRET" not in repr(transport)


@pytest.mark.anyio
async def test_an_error_answer_is_a_transport_error_naming_the_post() -> None:
    client = MockHttpClient(
        JsonMockResponse({"description": "testDescription", "error_code": 400}, {"http_code": 400})
    )

    with pytest.raises(TransportError) as raised:
        _ = await _transport(client, "testChannel").send(ChatMessage("testMessage"))

    assert str(raised.value) == "Unable to post the Telegram message: testDescription (code 400)."


@pytest.mark.anyio
async def test_an_error_answer_to_an_edit_names_the_edit() -> None:
    client = MockHttpClient(
        JsonMockResponse({"description": "testDescription", "error_code": 404}, {"http_code": 400})
    )

    with pytest.raises(TransportError) as raised:
        _ = await _transport(client, "testChannel").send(
            ChatMessage("testMessage", TelegramOptions().edit(123).to_options())
        )

    assert str(raised.value) == "Unable to edit the Telegram message: testDescription (code 404)."


@pytest.mark.anyio
async def test_an_error_answer_to_a_callback_query_names_the_answer() -> None:
    client = MockHttpClient(
        JsonMockResponse({"description": "QUERY_ID_INVALID", "error_code": 400}, {"http_code": 400})
    )

    with pytest.raises(TransportError) as raised:
        _ = await _transport(client).send(
            ChatMessage("ok", TelegramOptions().answer_callback_query("123").to_options())
        )

    assert str(raised.value) == (
        "Unable to answer callback query the Telegram message: QUERY_ID_INVALID (code 400)."
    )


@pytest.mark.anyio
async def test_an_unreachable_server_is_a_transport_error() -> None:
    client = MockHttpClient(MockResponse(info={"error": "Could not resolve host."}))

    with pytest.raises(TransportError, match=r"^Could not reach the remote Telegram server\.$"):
        _ = await _transport(client, "testChannel").send(ChatMessage("testMessage"))


@pytest.mark.anyio
async def test_it_posts_a_message_and_reports_its_id() -> None:
    client = _expecting(
        "sendMessage", {"chat_id": "testChannel", "text": "testMessage", "parse_mode": "MarkdownV2"}
    )

    sent = await _transport(client, "testChannel").send(ChatMessage("testMessage"))

    assert sent.message_id == "1"
    assert sent.transport == "telegram://api.telegram.org?channel=testChannel"


@pytest.mark.anyio
async def test_it_posts_over_http_when_ssl_is_off() -> None:
    def answer(_method: str, url: str, _options: RequestOptions) -> MockResponse:
        assert url == "http://api.telegram.org/bottoken/sendMessage"
        return _sent()

    _ = await _transport(MockHttpClient(answer), "c", False).send(ChatMessage("Hi"))


@pytest.mark.anyio
async def test_it_reports_no_id_when_the_answer_carries_none() -> None:
    client = MockHttpClient(JsonMockResponse({"ok": True, "result": True}))

    sent = await _transport(client, "testChannel").send(ChatMessage("testMessage"))

    assert sent.message_id is None


@pytest.mark.anyio
async def test_it_reports_no_id_when_the_result_carries_none() -> None:
    client = MockHttpClient(JsonMockResponse({"ok": True, "result": {"chat": {}}}))

    sent = await _transport(client, "testChannel").send(ChatMessage("testMessage"))

    assert sent.message_id is None


@pytest.mark.anyio
async def test_a_missing_upload_is_refused_before_any_request() -> None:
    options = TelegramOptions().upload_photo(FIXTURE_FILE).upload_document("/missing/file.pdf")

    with pytest.raises(FileNotFoundError):
        _ = await _transport(_never_called(), "c").send(ChatMessage("Hi", options.to_options()))


@pytest.mark.anyio
async def test_it_edits_a_message_text() -> None:
    client = _expecting(
        "editMessageText",
        {
            "chat_id": "testChannel",
            "message_id": 123,
            "text": "testMessage",
            "parse_mode": "MarkdownV2",
        },
    )

    _ = await _transport(client, "testChannel").send(
        ChatMessage("testMessage", TelegramOptions().edit(123).to_options())
    )


def _edit_media_cases() -> list[tuple[TelegramOptions, dict[str, object]]]:
    cases: list[tuple[TelegramOptions, dict[str, object]]] = []
    setters: dict[str, tuple[Callable[[TelegramOptions, str], TelegramOptions], str]] = {
        "photo": (TelegramOptions.photo, "https://localhost/photo.png"),
        "video": (TelegramOptions.video, "https://localhost/video.mp4"),
        "document": (TelegramOptions.document, "https://localhost/document.odt"),
        "audio": (TelegramOptions.audio, "https://localhost/audio.ogg"),
        "animation": (TelegramOptions.animation, "https://localhost/animation.gif"),
    }
    for media_type, (setter, url) in setters.items():
        for media in (url, "ABCDEF"):
            expected: dict[str, object] = {
                "type": media_type,
                "media": media,
                "caption": "testMessage",
                "parse_mode": "MarkdownV2",
            }
            cases.append((setter(TelegramOptions().edit(123), media), expected))
    return cases


@pytest.mark.parametrize(("options", "expected_media"), _edit_media_cases())
@pytest.mark.anyio
async def test_it_edits_a_message_media(
    options: TelegramOptions, expected_media: dict[str, object]
) -> None:
    client = _expecting(
        "editMessageMedia", {"chat_id": "testChannel", "message_id": 123, "media": expected_media}
    )

    _ = await _transport(client, "testChannel").send(
        ChatMessage("testMessage", options.to_options())
    )


@pytest.mark.anyio
async def test_editing_a_media_escapes_its_caption_once() -> None:
    client = _expecting(
        "editMessageMedia",
        {
            "chat_id": "testChannel",
            "message_id": 123,
            "media": {
                "type": "photo",
                "media": "https://localhost/photo.png",
                "caption": "I contain a \\. and a \\!",
                "parse_mode": "MarkdownV2",
            },
        },
    )
    options = TelegramOptions().edit(123).photo("https://localhost/photo.png")

    _ = await _transport(client, "testChannel").send(
        ChatMessage("I contain a . and a !", options.to_options())
    )


@pytest.mark.anyio
async def test_it_edits_a_message_caption() -> None:
    client = _expecting(
        "editMessageCaption",
        {
            "chat_id": "testChannel",
            "message_id": 123,
            "caption": "testMessage",
            "parse_mode": "MarkdownV2",
        },
    )

    _ = await _transport(client, "testChannel").send(
        ChatMessage("testMessage", TelegramOptions().edit_caption(123).to_options())
    )


@pytest.mark.anyio
async def test_editing_a_media_moves_the_spoiler_into_the_media() -> None:
    client = _expecting(
        "editMessageMedia",
        {
            "chat_id": "testChannel",
            "message_id": 123,
            "media": {
                "type": "photo",
                "media": "https://localhost/photo.png",
                "caption": "testMessage",
                "parse_mode": "MarkdownV2",
                "has_spoiler": True,
            },
        },
    )
    options = TelegramOptions().edit(123).photo("https://localhost/photo.png").has_spoiler(True)

    _ = await _transport(client, "testChannel").send(
        ChatMessage("testMessage", options.to_options())
    )


@pytest.mark.anyio
async def test_editing_a_media_keeps_the_reply_markup_at_the_top() -> None:
    markup = InlineKeyboardMarkup().inline_keyboard(
        [InlineKeyboardButton("Click").callback_data("click")]
    )
    client = _expecting(
        "editMessageMedia",
        {
            "chat_id": "testChannel",
            "message_id": 123,
            "reply_markup": {"inline_keyboard": [[{"text": "Click", "callback_data": "click"}]]},
            "media": {
                "type": "photo",
                "media": "https://localhost/photo.png",
                "caption": "testMessage",
                "parse_mode": "MarkdownV2",
            },
        },
    )
    options = TelegramOptions().edit(123).photo("https://localhost/photo.png").reply_markup(markup)

    _ = await _transport(client, "testChannel").send(
        ChatMessage("testMessage", options.to_options())
    )


@pytest.mark.anyio
async def test_editing_a_caption_in_html_does_not_escape_it() -> None:
    client = _expecting(
        "editMessageCaption",
        {
            "chat_id": "testChannel",
            "message_id": 123,
            "caption": "I contain a . and a !",
            "parse_mode": "HTML",
        },
    )
    options = TelegramOptions().parse_mode(TelegramOptions.PARSE_MODE_HTML).edit_caption(123)

    _ = await _transport(client, "testChannel").send(
        ChatMessage("I contain a . and a !", options.to_options())
    )


@pytest.mark.anyio
async def test_editing_a_message_with_an_uploaded_media_is_refused() -> None:
    options = TelegramOptions().edit(123).upload_photo(FIXTURE_FILE)

    with pytest.raises(
        LogicError, match=r"^Editing a message with a locally uploaded media is not supported yet"
    ):
        _ = await _transport(_never_called(), "testChannel").send(
            ChatMessage("testMessage", options.to_options())
        )


@pytest.mark.anyio
async def test_it_answers_a_callback_query() -> None:
    client = _expecting(
        "answerCallbackQuery",
        {
            "callback_query_id": "123",
            "show_alert": True,
            "cache_time": 1,
            "chat_id": "testChannel",
            "text": "testMessage",
            "parse_mode": "MarkdownV2",
        },
    )

    _ = await _transport(client, "testChannel").send(
        ChatMessage(
            "testMessage", TelegramOptions().answer_callback_query("123", True, 1).to_options()
        )
    )


@pytest.mark.anyio
async def test_the_options_chat_wins_over_the_dsn_channel() -> None:
    client = _expecting(
        "sendMessage",
        {"chat_id": "channelOverride", "text": "testMessage", "parse_mode": "MarkdownV2"},
    )

    sent = await _transport(client, "defaultChannel").send(
        ChatMessage("testMessage", TelegramOptions().chat_id("channelOverride").to_options())
    )

    assert sent.transport == "telegram://api.telegram.org?channel=defaultChannel"


@pytest.mark.anyio
async def test_it_escapes_the_reserved_characters_of_a_markdown_message() -> None:
    client = _expecting(
        "sendMessage",
        {
            "chat_id": "testChannel",
            "text": (
                "I contain special characters _ * [ ] ( ) ~ ` \\> \\# \\+ \\- \\= \\| \\{ \\} "
                "\\. \\! \\ to send\\."
            ),
            "parse_mode": "MarkdownV2",
        },
    )

    _ = await _transport(client, "testChannel").send(
        ChatMessage("I contain special characters _ * [ ] ( ) ~ ` > # + - = | { } . ! \\ to send.")
    )


def _url_cases() -> list[FileCase]:
    upload = "https://localhost/"
    return [
        (
            TelegramOptions().photo(f"{upload}photo.png").has_spoiler(True),
            "sendPhoto",
            [
                ("photo", f"{upload}photo.png"),
                ("has_spoiler", True),
                ("chat_id", "testChannel"),
                ("parse_mode", "MarkdownV2"),
                ("caption", "testMessage"),
            ],
        ),
        *(
            (
                setter(TelegramOptions(), f"{upload}{name}"),
                endpoint,
                [
                    (option, f"{upload}{name}"),
                    ("chat_id", "testChannel"),
                    ("parse_mode", "MarkdownV2"),
                    ("caption", "testMessage"),
                ],
            )
            for setter, option, endpoint, name in (
                (TelegramOptions.video, "video", "sendVideo", "video.mp4"),
                (TelegramOptions.animation, "animation", "sendAnimation", "animation.gif"),
                (TelegramOptions.audio, "audio", "sendAudio", "audio.ogg"),
                (TelegramOptions.document, "document", "sendDocument", "document.odt"),
            )
        ),
        (
            TelegramOptions().sticker(f"{upload}sticker.webp", "🤖"),
            "sendSticker",
            [
                ("sticker", f"{upload}sticker.webp"),
                ("emoji", "🤖"),
                ("chat_id", "testChannel"),
                ("parse_mode", "MarkdownV2"),
            ],
        ),
        (
            TelegramOptions().sticker(f"{upload}sticker.webp"),
            "sendSticker",
            [
                ("sticker", f"{upload}sticker.webp"),
                ("chat_id", "testChannel"),
                ("parse_mode", "MarkdownV2"),
            ],
        ),
    ]


def _file_id_cases() -> list[FileCase]:
    return [
        (
            TelegramOptions().photo("ABCDEF").has_spoiler(True),
            "sendPhoto",
            [
                ("photo", "ABCDEF"),
                ("has_spoiler", True),
                ("chat_id", "testChannel"),
                ("parse_mode", "MarkdownV2"),
                ("caption", "testMessage"),
            ],
        ),
        *(
            (
                setter(TelegramOptions(), "ABCDEF"),
                endpoint,
                [
                    (option, "ABCDEF"),
                    ("chat_id", "testChannel"),
                    ("parse_mode", "MarkdownV2"),
                    ("caption", "testMessage"),
                ],
            )
            for setter, option, endpoint in (
                (TelegramOptions.video, "video", "sendVideo"),
                (TelegramOptions.animation, "animation", "sendAnimation"),
                (TelegramOptions.audio, "audio", "sendAudio"),
                (TelegramOptions.document, "document", "sendDocument"),
            )
        ),
    ]


@pytest.mark.parametrize(("options", "endpoint", "expected"), [*_url_cases(), *_file_id_cases()])
@pytest.mark.anyio
async def test_it_sends_a_file_by_url_or_file_id(
    options: TelegramOptions, endpoint: str, expected: Sequence[tuple[str, object]]
) -> None:
    def answer(_method: str, url: str, request: RequestOptions) -> MockResponse:
        assert url.endswith(f"/{endpoint}")
        body = request.get("json")
        assert isinstance(body, dict)
        assert list(cast("dict[str, object]", body).items()) == list(expected)
        return _sent()

    sent = await _transport(MockHttpClient(answer), "testChannel").send(
        ChatMessage("testMessage", options.to_options())
    )

    assert sent.message_id == "1"
    assert sent.transport == "telegram://api.telegram.org?channel=testChannel"


def _upload_cases() -> list[tuple[TelegramOptions, str, str, dict[str, object]]]:
    text: dict[str, object] = {
        "chat_id": "testChannel",
        "parse_mode": "MarkdownV2",
        "caption": "testMessage",
    }
    return [
        (
            TelegramOptions().upload_photo(FIXTURE_FILE).has_spoiler(True),
            "sendPhoto",
            "photo",
            {"has_spoiler": True, **text},
        ),
        (TelegramOptions().upload_video(FIXTURE_FILE), "sendVideo", "video", text),
        (TelegramOptions().upload_animation(FIXTURE_FILE), "sendAnimation", "animation", text),
        (TelegramOptions().upload_audio(FIXTURE_FILE), "sendAudio", "audio", text),
        (TelegramOptions().upload_document(FIXTURE_FILE), "sendDocument", "document", text),
        (
            TelegramOptions().upload_sticker(FIXTURE_FILE, "🤖"),
            "sendSticker",
            "sticker",
            {"emoji": "🤖", "chat_id": "testChannel", "parse_mode": "MarkdownV2"},
        ),
        (
            TelegramOptions().upload_sticker(FIXTURE_FILE),
            "sendSticker",
            "sticker",
            {"chat_id": "testChannel", "parse_mode": "MarkdownV2"},
        ),
    ]


@pytest.mark.parametrize(("options", "endpoint", "file_option", "expected"), _upload_cases())
@pytest.mark.anyio
async def test_it_uploads_a_file_as_a_form_body_and_closes_it(
    options: TelegramOptions, endpoint: str, file_option: str, expected: dict[str, object]
) -> None:
    closed: list[Callable[[], bool]] = []

    def answer(_method: str, url: str, request: RequestOptions) -> MockResponse:
        assert url.endswith(f"/{endpoint}")
        assert request.get("json") is None
        body = request.get("body")
        assert isinstance(body, dict)
        upload = body.pop(file_option)
        assert isinstance(upload, BufferedReader)
        assert not upload.closed
        assert upload.name == FIXTURE_FILE
        assert upload.read() == Path(FIXTURE_FILE).read_bytes()
        assert body == expected
        closed.append(lambda: upload.closed)
        return _sent()

    sent = await _transport(MockHttpClient(answer), "testChannel").send(
        ChatMessage("testMessage", options.to_options())
    )

    assert sent.message_id == "1"
    assert [is_closed() for is_closed in closed] == [True]


@pytest.mark.anyio
async def test_an_uploaded_file_is_closed_when_the_send_fails() -> None:
    uploaded: list[object] = []

    def answer(_method: str, _url: str, request: RequestOptions) -> MockResponse:
        body = request.get("body")
        assert isinstance(body, dict)
        uploaded.append(body["photo"])
        return MockResponse(info={"error": "Connection reset."})

    with pytest.raises(TransportError):
        _ = await _transport(MockHttpClient(answer), "c").send(
            ChatMessage("Hi", TelegramOptions().upload_photo(FIXTURE_FILE).to_options())
        )

    assert [isinstance(upload, BufferedReader) and upload.closed for upload in uploaded] == [True]


@pytest.mark.anyio
async def test_it_sends_a_location() -> None:
    client = _expecting(
        "sendLocation",
        {
            "chat_id": "testChannel",
            "parse_mode": "MarkdownV2",
            "latitude": 48.8566,
            "longitude": 2.3522,
        },
    )

    sent = await _transport(client, "testChannel").send(
        ChatMessage("", TelegramOptions().location(48.8566, 2.3522).to_options())
    )

    assert sent.message_id == "1"


@pytest.mark.anyio
async def test_it_sends_a_venue() -> None:
    client = _expecting(
        "sendVenue",
        {
            "chat_id": "testChannel",
            "parse_mode": "MarkdownV2",
            "latitude": 48.8566,
            "longitude": 2.3522,
            "title": "Center of Paris",
            "address": "France, Paris",
        },
    )
    options = TelegramOptions().venue(48.8566, 2.3522, "Center of Paris", "France, Paris")

    _ = await _transport(client, "testChannel").send(ChatMessage("", options.to_options()))


@pytest.mark.anyio
async def test_it_sends_a_contact() -> None:
    v_card = (
        "BEGIN:VCARD\nVERSION:3.0\nN:Doe;John;;;\nFN:John Doe\n"
        "EMAIL;type=INTERNET;type=WORK;type=pref:johnDoe@example.org\n"
        "TEL;type=WORK;type=pref:+330186657200\nEND:VCARD"
    )
    client = _expecting(
        "sendContact",
        {
            "chat_id": "testChannel",
            "parse_mode": "MarkdownV2",
            "phone_number": "+330186657200",
            "first_name": "John",
            "last_name": "Doe",
            "vcard": v_card,
        },
    )
    options = TelegramOptions().contact("+330186657200", "John", "Doe", v_card)

    _ = await _transport(client, "testChannel").send(ChatMessage("", options.to_options()))


def _exclusive_cases() -> list[TelegramOptions]:
    return [
        TelegramOptions().edit(1).answer_callback_query(""),
        TelegramOptions().edit(1).location(48.8566, 2.3522),
        TelegramOptions().edit(1).sticker(""),
        TelegramOptions().edit(1).photo("").video(""),
        TelegramOptions().answer_callback_query("").video(""),
        TelegramOptions().photo("").video(""),
        TelegramOptions().location(48.8566, 2.3522).video(""),
        TelegramOptions().audio("").video(""),
        TelegramOptions().document("").video(""),
        TelegramOptions().video("").animation(""),
        TelegramOptions().animation("").video(""),
        TelegramOptions().venue(48.8566, 2.3522, "", "").video(""),
        TelegramOptions().contact("", "").video(""),
        TelegramOptions().sticker("").video(""),
        TelegramOptions().upload_photo(FIXTURE_FILE).video(""),
        TelegramOptions().upload_audio(FIXTURE_FILE).video(""),
        TelegramOptions().upload_document(FIXTURE_FILE).video(""),
        TelegramOptions().upload_video(FIXTURE_FILE).animation(""),
        TelegramOptions().upload_animation(FIXTURE_FILE).video(""),
        TelegramOptions().upload_sticker(FIXTURE_FILE).video(""),
    ]


@pytest.mark.parametrize("options", _exclusive_cases())
@pytest.mark.anyio
async def test_exclusive_options_used_together_are_refused(options: TelegramOptions) -> None:
    with pytest.raises(MultipleExclusiveOptionsUsedError):
        _ = await _transport(_never_called(), "testChannel").send(
            ChatMessage("", options.to_options())
        )


@pytest.mark.anyio
async def test_the_refusal_names_the_exclusive_options_used() -> None:
    with pytest.raises(MultipleExclusiveOptionsUsedError) as raised:
        _ = await _transport(_never_called()).send(
            ChatMessage("", TelegramOptions().photo("a").video("b").to_options())
        )

    assert raised.value.used_exclusive_options == ("photo", "video")
    assert raised.value.exclusive_options == TelegramTransport.EXCLUSIVE_OPTIONS
