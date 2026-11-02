"""Plain data written as JSON text and read back, refusing what JSON cannot carry exactly."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from pydantic import ValidationError
from pydantic_core import PydanticSerializationError, from_json, to_json
from typing_extensions import override

from xtr_serializer._loc_path import render_path
from xtr_serializer._plain_data import PLAIN_DATA
from xtr_serializer._type_names import qualified_name_of
from xtr_serializer.exception import (
    InvalidArgumentError,
    NotEncodableValueError,
    UnsupportedFormatError,
)

from .decoder_interface import DecoderInterface
from .encoder_interface import EncoderInterface
from .json_encoder_keys import JSON_INDENT

if TYPE_CHECKING:
    from xtr_serializer.context.context import Context
    from xtr_serializer.normalized_value import NormalizedValue

__all__ = ["JsonEncoder"]

# Wider reads no easier. And the writer lays out the whole indent before it writes a byte: a count
# too large to lay out does not raise an error, it panics or ends the process.
_MAX_INDENT: Final = 10


@final
class JsonEncoder(EncoderInterface, DecoderInterface):
    """Writes plain data as JSON text and reads it back, refusing what JSON cannot carry exactly.

    A looser writer puts down NaN as ``NaN``, the key ``1`` as ``"1"``, a tuple as a list, and the
    data reads back changed. Here pydantic's JSON check refuses those and cycles, and the text
    written is read once before it is returned, so what would not read back is refused too:
    nesting deeper than the parser goes, an integer longer than it reads. Reading refuses text
    that is not JSON, ``NaN`` and the infinities included.

    Each refusal is a :class:`NotEncodableValueError` saying what is wrong, never quoting the
    data. A refusal by the check also says where: the path of keys and indexes leading to the
    refused value — the keys of a mapping are the data's structure, as the names of attributes
    are, so they are shown, but not a key that is itself what is refused. A refusal of text that
    would not read back gives the parser's reason alone: the place the parser names is in text
    the caller never sees, and how far into it that place is would tell how long the values
    before it are. Text that is read is refused saying where in it the parser stopped. A call's
    context wins over the default one.
    """

    FORMAT: Final = "json"

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
        if indent is not None and (type(indent) is not int or not 0 <= indent <= _MAX_INDENT):
            raise InvalidArgumentError(
                f"{JSON_INDENT!r} must be a count of spaces from 0 to {_MAX_INDENT}, or None"
            )
        try:
            text = to_json(PLAIN_DATA.validate_python(data), indent=indent)
            from_json(text)  # the check passes nesting and integers the parser cannot read
        except ValidationError as error:
            refusal = _refusal(error)
        except PydanticSerializationError:  # past the check, only a lone surrogate fails here
            refusal = "a string in the data has no UTF-8 form"
        except ValueError as error:  # the parser says why, then the line and column it stopped at
            reason, _, _ = str(error).partition(" at line ")
            refusal = f"the JSON written would not read back: {reason}"
        else:
            return text.decode()
        # Raised outside the handler, so no exception holding the data is chained to it.
        raise NotEncodableValueError(refusal) from None

    @override
    def decode(
        self, data: str | bytes, format: str, context: Context | None = None
    ) -> NormalizedValue:
        if format != self.FORMAT:
            raise UnsupportedFormatError(format)
        try:
            # The parser refuses the literals NaN and Infinity; the check, 1e999 read as infinity.
            decoded = PLAIN_DATA.validate_python(from_json(data, allow_inf_nan=False))
        except ValidationError as error:
            refusal = _refusal(error)
        except ValueError as error:  # the parser says why and where, never what the text was
            refusal = f"the text is not valid JSON: {error}"
        except TypeError:  # the parser takes no str holding a lone surrogate, and nothing but text
            refusal = (
                "the text has no UTF-8 form"
                if isinstance(data, str)
                else f"only str or bytes can be read, not {qualified_name_of(type(data))!r}"
            )
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
