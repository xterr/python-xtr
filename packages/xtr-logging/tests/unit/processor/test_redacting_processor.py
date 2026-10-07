from __future__ import annotations

from dataclasses import dataclass
from typing import final

from typing_extensions import override
from xtr_logging_contracts import EXCEPTION_KEY

from tests.support.records import make_record
from xtr_logging.formatter.line_formatter import LineFormatter
from xtr_logging.processor.redacting_processor import RedactingProcessor


def test_it_masks_values_whose_key_matches_a_default_pattern() -> None:
    processor = RedactingProcessor()
    record = make_record(
        context={"password": "hunter2", "Authorization": "Bearer x", "user": "ada"},
    )

    result = processor(record)

    assert result.context["password"] == "[redacted]"
    assert result.context["Authorization"] == "[redacted]"
    assert result.context["user"] == "ada"


def test_it_masks_matching_keys_recursively_in_nested_mappings_and_lists() -> None:
    processor = RedactingProcessor()
    record = make_record(
        context={"outer": {"api_key": "k", "items": [{"secret": "s"}, {"keep": "v"}]}},
    )

    result = processor(record)

    assert dict(result.context) == {
        "outer": {
            "api_key": "[redacted]",
            "items": [{"secret": "[redacted]"}, {"keep": "v"}],
        },
    }


def test_it_masks_matching_keys_in_extra_too() -> None:
    processor = RedactingProcessor()
    record = make_record(extra={"token": "t"})

    result = processor(record)

    assert result.extra["token"] == "[redacted]"


def test_it_masks_values_matching_a_value_pattern() -> None:
    processor = RedactingProcessor(values=(r"\d{16}",))
    record = make_record(context={"note": "card 4111111111111111 used"})

    result = processor(record)

    assert result.context["note"] == "card [redacted] used"


def test_a_nested_mapping_with_non_string_keys_is_still_redacted() -> None:
    processor = RedactingProcessor(values=("hunter2",))
    record = make_record(context={"outer": {1: "hunter2", "password": "p"}})

    result = processor(record)

    assert result.context["outer"] == {1: "[redacted]", "password": "[redacted]"}


def test_value_patterns_redact_the_message_too() -> None:
    processor = RedactingProcessor(values=(r"\d{16}",))
    record = make_record(message="charged card 4111111111111111")

    result = processor(record)

    assert result.message == "charged card [redacted]"


def test_value_patterns_redact_bytes_values() -> None:
    processor = RedactingProcessor(values=(r"\d{16}",))
    record = make_record(context={"raw": b"card 4111111111111111"})

    result = processor(record)

    assert result.context["raw"] == b"card [redacted]"


def test_bytes_without_a_match_are_returned_untouched() -> None:
    processor = RedactingProcessor(values=(r"\d{16}",))
    payload = b"\xff\xfe nothing secret"
    record = make_record(context={"raw": payload})

    result = processor(record)

    assert result.context["raw"] is payload


def test_value_patterns_redact_bytearray_values() -> None:
    processor = RedactingProcessor(values=(r"\d{16}",))
    record = make_record(context={"raw": bytearray(b"card 4111111111111111")})

    result = processor(record)

    assert result.context["raw"] == b"card [redacted]"


def test_a_bytearray_without_a_match_stays_an_untouched_bytearray() -> None:
    processor = RedactingProcessor(values=(r"\d{16}",))
    payload = bytearray(b"\xff\xfe nothing secret")
    record = make_record(context={"raw": payload})

    result = processor(record)

    assert result.context["raw"] is payload
    assert isinstance(result.context["raw"], bytearray)


def test_sets_are_redacted_like_lists() -> None:
    processor = RedactingProcessor(values=(r"\d{16}",))
    record = make_record(context={"cards": {"4111111111111111"}})

    result = processor(record)

    assert result.context["cards"] == ["[redacted]"]


def test_it_leaves_a_record_without_sensitive_data_untouched() -> None:
    processor = RedactingProcessor()
    record = make_record(context={"user": "ada"})

    result = processor(record)

    assert result.context["user"] == "ada"


def _raise(error: BaseException) -> None:
    raise error


def _raised(error: BaseException) -> BaseException:
    try:
        _raise(error)
    except BaseException as caught:  # noqa: BLE001 — the test wants the raised error back, traceback and all
        return caught
    return error


def test_value_patterns_redact_a_logged_exceptions_message() -> None:
    processor = RedactingProcessor(values=(r"\d{16}",))
    error = _raised(ValueError("card 4111111111111111 declined"))
    record = make_record(context={EXCEPTION_KEY: error})

    result = processor(record)

    redacted = result.context[EXCEPTION_KEY]
    assert isinstance(redacted, ValueError)
    assert str(redacted) == "card [redacted] declined"
    assert redacted.__traceback__ is error.__traceback__


def test_an_exception_whose_text_matches_the_key_pattern_is_masked() -> None:
    processor = RedactingProcessor()
    record = make_record(context={EXCEPTION_KEY: RuntimeError("password=hunter2 rejected")})

    result = processor(record)

    redacted = result.context[EXCEPTION_KEY]
    assert isinstance(redacted, RuntimeError)
    assert str(redacted) == "[redacted]"


def test_the_cause_of_a_logged_exception_is_redacted_too() -> None:
    processor = RedactingProcessor(values=("hunter2",))
    error = RuntimeError("login failed")
    error.__cause__ = ValueError("bad hunter2")
    record = make_record(context={"error": error})

    result = processor(record)

    redacted = result.context["error"]
    assert isinstance(redacted, BaseException)
    assert str(redacted.__cause__) == "bad [redacted]"


def test_an_exception_without_a_secret_is_returned_as_it_is() -> None:
    processor = RedactingProcessor(values=("hunter2",))
    error = ValueError("nothing here")
    record = make_record(context={EXCEPTION_KEY: error})

    result = processor(record)

    assert result.context[EXCEPTION_KEY] is error


@final
class _UnrebuildableError(Exception):
    def __init__(self, secret: str, *, code: int) -> None:
        super().__init__(secret)
        self.code = code

    @override
    def __reduce__(self) -> str | tuple[object, ...]:
        raise TypeError


def test_an_exception_that_cannot_be_copied_is_replaced_by_its_redacted_text() -> None:
    processor = RedactingProcessor(values=("hunter2",))
    record = make_record(context={"error": _UnrebuildableError("leaked hunter2", code=1)})

    result = processor(record)

    redacted = result.context["error"]
    assert isinstance(redacted, BaseException)
    assert "hunter2" not in str(redacted)
    assert "leaked [redacted]" in str(redacted)


@dataclass(frozen=True)
class _Credentials:
    user: str
    password: str
    note: str


def test_a_dataclass_is_redacted_by_field_name_and_value() -> None:
    processor = RedactingProcessor(values=("hunter2",))
    record = make_record(context={"login": _Credentials("ada", "pw", "typed hunter2")})

    result = processor(record)

    assert result.context["login"] == {
        f"{__name__}._Credentials": {
            "user": "ada",
            "password": "[redacted]",
            "note": "typed [redacted]",
        },
    }


@final
class _Printable:
    @override
    def __str__(self) -> str:
        return "session hunter2"


def test_value_patterns_redact_the_text_of_any_other_object() -> None:
    processor = RedactingProcessor(values=("hunter2",))
    record = make_record(context={"session": _Printable()})

    result = processor(record)

    assert result.context["session"] == "session [redacted]"


def test_an_other_object_without_a_match_is_returned_as_it_is() -> None:
    processor = RedactingProcessor(values=("absent",))
    value = _Printable()
    record = make_record(context={"session": value})

    result = processor(record)

    assert result.context["session"] is value


def test_a_bytes_key_matching_the_key_pattern_is_masked() -> None:
    processor = RedactingProcessor()
    record = make_record(context={"outer": {b"password": "hunter2", b"user": "ada"}})

    result = processor(record)

    assert result.context["outer"] == {b"password": "[redacted]", b"user": "ada"}


def test_value_patterns_redact_a_top_level_key() -> None:
    """A secret used as the name of an extra was written out whole: the keys
    of a mapping were never run through the value patterns."""
    processor = RedactingProcessor(values=("hunter2",))
    record = make_record(extra={"token-hunter2": "x"})

    result = processor(record)

    assert dict(result.extra) == {"token-[redacted]": "[redacted]"}


def test_value_patterns_redact_a_nested_key() -> None:
    processor = RedactingProcessor(values=("hunter2",))
    record = make_record(context={"outer": {"id-hunter2": "ada"}})

    result = processor(record)

    assert result.context["outer"] == {"id-[redacted]": "ada"}


def test_value_patterns_redact_a_bytes_key() -> None:
    processor = RedactingProcessor(values=("hunter2",))
    record = make_record(context={"outer": {b"id-hunter2": "ada"}})

    result = processor(record)

    assert result.context["outer"] == {b"id-[redacted]": "ada"}


def test_a_key_that_is_not_text_comes_back_as_it_is() -> None:
    processor = RedactingProcessor(values=("hunter2",))
    record = make_record(context={"outer": {7: "ada"}})

    result = processor(record)

    assert result.context["outer"] == {7: "ada"}


def test_an_exception_chain_that_loops_back_leaks_nothing() -> None:
    """The cycle-breaker handed back the original exception, so the loop
    re-attached it unredacted and a formatter wrote the secret out."""
    processor = RedactingProcessor(values=("hunter2",))
    outer = RuntimeError("outer hunter2")
    inner = ValueError("inner hunter2")
    outer.__cause__ = inner
    inner.__cause__ = outer
    record = make_record(context={EXCEPTION_KEY: outer})

    formatted = LineFormatter().format(processor(record))

    assert "hunter2" not in formatted
