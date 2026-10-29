"""Plain data written as JSON text and read back, refusing what JSON cannot carry exactly."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast, final

from pydantic import ConfigDict, JsonValue, TypeAdapter, ValidationError
from pydantic_core import PydanticSerializationError, from_json, to_json
from typing_extensions import override

from xtr_serializer._loc_path import render_path
from xtr_serializer.exception import (
    InvalidArgumentError,
    NotEncodableValueError,
    UnsupportedFormatError,
)

from .decoder_interface import DecoderInterface
from .encoder_interface import EncoderInterface
from .json_encoder_keys import JSON_ALLOW_INF_NAN, JSON_INDENT

if TYPE_CHECKING:
    from xtr_serializer.context.context import Context
    from xtr_serializer.normalized_value import NormalizedValue

__all__ = ["JsonEncoder"]

# Strict: only JSON's own types pass, not a tuple or a set. Finite: NaN and infinity are refused.
_JSON_VALUE: Final[TypeAdapter[JsonValue]] = TypeAdapter(
    JsonValue, config=ConfigDict(strict=True, allow_inf_nan=False)
)


@final
class JsonEncoder(EncoderInterface, DecoderInterface):
    """Writes plain data as JSON text and reads it back, refusing what JSON cannot carry exactly.

    A looser writer puts down NaN as ``NaN``, the key ``1`` as ``"1"``, a tuple as a list, and the
    data reads back changed. Here pydantic's JSON check refuses those, cycles and nesting too deep
    to check, and reading refuses text that is not JSON, each with :class:`NotEncodableValueError`
    saying where and what is wrong, never the value. A call's context wins over the default one.
    """

    FORMAT: Final = "json"

    __slots__ = ("_default_context",)

    def __init__(self, default_context: Context | None = None) -> None:
        """Keep a copy of ``default_context``, so later changes to it are not picked up."""
        self._default_context = dict(default_context or {})

    @override
    def supports_encoding(self, format: str) -> bool:
        return format == self.FORMAT

    @override
    def supports_decoding(self, format: str) -> bool:
        return format == self.FORMAT

    @override
    def encode(self, data: NormalizedValue, format: str, context: Context | None = None) -> str:
        if format != self.FORMAT:
            raise UnsupportedFormatError(format)
        indent = {**self._default_context, **(context or {})}.get(JSON_INDENT)
        if indent is not None and (type(indent) is not int or indent < 0):
            raise InvalidArgumentError(f"{JSON_INDENT!r} must be a count of spaces or None")
        try:
            return to_json(_JSON_VALUE.validate_python(data), indent=indent).decode()
        except ValidationError as error:
            refusal = _refusal(error)
        except PydanticSerializationError:  # past the check, only a lone surrogate fails here
            refusal = "a string in the data has no UTF-8 form"
        # Raised outside the handler, so no exception holding the data is chained to it.
        raise NotEncodableValueError(refusal) from None

    @override
    def decode(
        self, data: str | bytes, format: str, context: Context | None = None
    ) -> NormalizedValue:
        if format != self.FORMAT:
            raise UnsupportedFormatError(format)
        allow = {**self._default_context, **(context or {})}.get(JSON_ALLOW_INF_NAN, False)
        if not isinstance(allow, bool):
            raise InvalidArgumentError(f"{JSON_ALLOW_INF_NAN!r} must be a bool")
        try:
            # Typed as returning anything, the parser returns plain JSON data and nothing else.
            decoded = cast("NormalizedValue", from_json(data, allow_inf_nan=allow))
            if not allow:  # refusing the literals does not stop 1e999 from reading as infinity
                decoded = _JSON_VALUE.validate_python(decoded)
        except ValidationError as error:
            refusal = _refusal(error)
        except ValueError as error:  # the parser says why and where, never what the text was
            refusal = f"the text is not valid JSON: {error}"
        except TypeError:  # the parser takes no str holding a lone surrogate
            refusal = "the text has no UTF-8 form"
        else:
            return decoded
        raise NotEncodableValueError(refusal) from None


def _refusal(error: ValidationError) -> str:
    """Say where pydantic's first error sits and what it is, without the value.

    ``loc`` alternates each JSON value's union tag with the key or index under it. A refused key
    ends it with ``"[key]"`` where a tag would be, and is left out: it is the refused value.
    """
    first = error.errors(include_url=False, include_context=False, include_input=False)[0]
    loc = first["loc"]
    key_refused = len(loc) % 2 == 1 and loc[-1] == "[key]"
    keys = loc[1:-2:2] if key_refused else loc[1::2]
    path = render_path(keys)
    location = f"at {path!r}: " if path else ""
    return f"{location}{'a key: ' if key_refused else ''}{first['msg']} [type={first['type']}]"
