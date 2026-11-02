"""Plain data read back before it is handed out, so what would not come back exact is refused."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from pydantic import ValidationError
from pydantic_core import to_json

from xtr_serializer._loc_path import render_path
from xtr_serializer._plain_data import PLAIN_DATA
from xtr_serializer._type_names import name_of, qualified_name_of
from xtr_serializer.exception import NotNormalizableValueError

from ._first_difference import first_difference
from ._validation_refusals import refusals_of

if TYPE_CHECKING:
    from collections.abc import Callable

    from pydantic_core import ErrorDetails

    from xtr_serializer.normalized_value import NormalizedValue

__all__ = ["read_back_refusal"]

_CHANGED: Final = (
    "it would read back changed: a field declaring no type, or a list or dict written without its "
    "declared type, holds a set, a tuple, an object or a key that is not a string; a value of a "
    "subclass, such as True or an enum member in an int "
    "field, reads back as the declared type; a datetime field holds a zone in an hour the clocks "
    "repeat, which ZonedDateTime keeps; or its type does not compare by value"
)

# Why reading back could not confirm the value, by the step that raised. The exception is named
# by its type alone: its message may quote the data.
_UNCONFIRMED: Final = {
    "not_json": "it has no JSON form to read back: it holds text JSON cannot carry, such as a "
    "lone surrogate",
    "not_read_back": "it could not be read back to confirm it is exact: reading it raised {}; a "
    "validator that needs the context to read needs it to write as well",
    "not_comparable": "it could not be compared with what it reads back as: the comparison "
    "raised {}",
}


def read_back_refusal(
    value: object,
    written: NormalizedValue,
    read: Callable[[bytes], object] | None,
    *,
    by_alias: bool,
) -> NotNormalizableValueError | None:
    """Say why ``written`` would not read back as ``value``, or ``None`` when it would.

    ``written`` is checked as the JSON encoder checks it first: a float holding NaN or infinity,
    which pydantic writes as it is where a model's own configuration allows them, has no JSON
    form. ``read`` is ``None`` for a write that is not to be read back, a partial one, which is
    only checked so.

    pydantic writes what it holds by the field's declared type, and where a field declares nothing
    — ``Any``, a bare ``list`` or ``dict`` — by what it finds: a set or a tuple as a list, a key
    that is not a string as one, a model as a mapping. It writes ``True`` in an ``int`` field as
    ``1``, and a decimal NaN, which it cannot read, as ``"NaN"``. None of that warns. Reading the
    data back with ``read`` and comparing, part by part and by exact type, finds all of it.
    What equality does not look at is not compared, so it is not confirmed either: a
    ``defaultdict``'s default factory or a ``deque``'s maximum length is not carried, and a value
    differing from what it reads back as only there is passed.

    A refusal says where: reading, from pydantic's location in ``written``; comparing, by the
    field names, keys and indexes leading to the part that differs, a field named by its alias
    when ``written`` is, ``by_alias``, as reading names it. A step that raises is a refusal too,
    naming what it raised and never its message. The refusal is returned, not raised, so no
    exception is chained to it.
    """
    steps: list[str | int] = []
    stage = "not_json"
    details: list[ErrorDetails] = []
    raised = ""
    try:
        text = to_json(PLAIN_DATA.validate_python(written))
        if read is None:
            return None
        stage = "not_read_back"
        read_value = read(text)
        stage = "not_comparable"
        changed = first_difference(value, read_value, steps, by_alias=by_alias)
    except ValidationError as error:
        details = error.errors(include_url=False)
    except Exception as error:  # noqa: BLE001 - whatever the data's code raises leaves it unconfirmed
        raised = name_of(type(error))
    else:
        if changed is None:
            return None
        return NotNormalizableValueError(
            _CHANGED,
            path=render_path(steps),
            current_type=qualified_name_of(changed),
            error_type="not_exact",
        )
    if details and stage == "not_json":
        first = details[0]
        return NotNormalizableValueError(
            f"it has no JSON form: {first['msg']}",
            path=render_path(first["loc"][1::2]),
            error_type=first["type"],
        )
    if details:
        first = refusals_of(details, written, plain=True)[0]
        return NotNormalizableValueError(
            f"it would not read back: {first.message}",
            path=first.path,
            error_type=first.error_type,
        )
    return NotNormalizableValueError(
        _UNCONFIRMED[stage].format(raised), path=render_path(steps), error_type=stage
    )
