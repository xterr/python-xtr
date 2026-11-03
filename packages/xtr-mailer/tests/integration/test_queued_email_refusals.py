"""What a broker hands a worker is untrusted: a forged queued email is refused, never echoed.

Every refusal is the bus's decoding error, says where the data did not fit, and repeats nothing
of what the data held. Upstream's unserialize guards are ported here as forged payloads:
``EmailTest::testUnserializeRejectsObjectInTypedCharsetProperty`` and
``testUnserializeRejectsNonStringCharset``, and
``RemoteTemplateEmailTest::testUnserializeRejectsInvalidTemplateSlot``. Reading is linear in
the size of the data.
"""

from __future__ import annotations

import contextlib
import json
from typing import TYPE_CHECKING, Final, cast

import pytest
from xtr_messenger import EncodedEnvelope, MessageDecodingFailedError, name_of
from xtr_mime import Email

from tests.support.growth import assert_linear_growth
from tests.support.queue import WIRE
from xtr_mailer import RemoteTemplateEmail
from xtr_mailer.messenger import SendEmailMessage
from xtr_mailer.messenger._wire import write

if TYPE_CHECKING:
    from collections.abc import Callable

_SECRET: Final = "SECRET\r\nBcc: victim@example.com\x00"
_TEXT_HEADER: Final = {"$type": "text", "charset": "utf-8", "language": None, "value": "v"}


def _decoded(body: str) -> object:
    return WIRE.decode(EncodedEnvelope(body, {"type": name_of(SendEmailMessage)})).message


def _refused(data: object) -> MessageDecodingFailedError:
    with pytest.raises(MessageDecodingFailedError) as raised:
        _ = _decoded(json.dumps(data))
    for error in (raised.value, raised.value.__cause__):
        shown = str(error)
        assert "SECRET" not in shown
        assert "victim" not in shown
        assert "passwd" not in shown
        assert "AAAAAAAAAA" not in shown
    return raised.value


def _email(**changed: object) -> dict[str, object]:
    written = write(Email().from_("a@example.com").to("b@example.com").text("t").html("h"), None)
    message = cast("dict[str, object]", written["message"])
    return {**written, "message": {**message, **changed}}


def _with_header(**header: object) -> dict[str, object]:
    return _email(headers={"line_length": 76, "fields": [{**_TEXT_HEADER, **header}]})


def test_a_forged_message_class_is_refused() -> None:
    _ = _refused(_email(**{"$type": _SECRET}))


@pytest.mark.parametrize(
    "name",
    ["X-A\r\nBcc: victim@example.com", "X-A\x00SECRET", "A" * 10_000, "SECRET:" + "A" * 300],
    ids=["line break", "null", "10k characters", "colon"],
)
def test_a_header_name_that_is_no_header_name_is_refused(name: str) -> None:
    _ = _refused(_with_header(name=name))


def test_a_forged_header_kind_is_refused() -> None:
    _ = _refused(_with_header(**{"name": "X-A", "$type": _SECRET}))


def test_a_path_attachment_is_refused_and_no_file_is_read() -> None:
    attachment = {"$type": "data", "path": "/etc/passwd", "filename": "passwd"}

    _ = _refused(_email(attachments=[attachment]))


def test_a_body_naming_a_path_is_refused() -> None:
    _ = _refused(_email(text={"path": "/etc/passwd"}))


def test_bad_base64_is_refused() -> None:
    _ = _refused({"version": 1, "message": {"$type": "raw", "body": _SECRET}, "envelope": None})


@pytest.mark.parametrize("charset", ["text_charset", "html_charset"])
@pytest.mark.parametrize(
    "value", [123, {"__str__": _SECRET}, [_SECRET]], ids=["int", "object", "list"]
)
def test_a_charset_that_is_not_text_is_refused(charset: str, value: object) -> None:
    _ = _refused(_email(**{charset: value}))


@pytest.mark.parametrize("template", [{"__str__": _SECRET}, _SECRET, ["welcome"]])
def test_a_template_of_the_wrong_shape_is_refused(template: object) -> None:
    written = write(RemoteTemplateEmail().template("welcome"), None)
    message = cast("dict[str, object]", written["message"])

    _ = _refused({**written, "message": {**message, "template": template}})


def test_deeply_nested_data_is_refused() -> None:
    nested = "[" * 100_000 + "]" * 100_000

    with pytest.raises(MessageDecodingFailedError):
        _ = _decoded(json.dumps(_email()).replace('"t"', nested, 1))


def test_a_version_this_mailer_does_not_read_is_refused() -> None:
    _ = _refused({**_email(), "version": 2})


def _many_headers(size: int) -> str:
    fields = [{**_TEXT_HEADER, "name": f"X-{index}"} for index in range(size)]
    return json.dumps(_email(headers={"line_length": 76, "fields": fields}))


def _long_value(size: int) -> str:
    return json.dumps(_with_header(name="X-A", value="é" * size))


def _long_name(size: int) -> str:
    return json.dumps(_with_header(name="A" * size))


@pytest.mark.parametrize("shape", [_many_headers, _long_value, _long_name], ids=str)
def test_reading_takes_time_linear_in_the_size_of_the_data(
    shape: Callable[[int], str],
) -> None:
    def run(size: int) -> None:
        body = shape(size)
        with contextlib.suppress(MessageDecodingFailedError):
            _ = _decoded(body)

    assert_linear_growth(run, 4_000)
