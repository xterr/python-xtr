"""Writing metadata values as diagram text.

Metadata holds any value, and a diagram holds only text. The rules here fix
how each kind of value reads once written, so every dump of a definition is
the same, byte for byte: a flag reads ``1``, nothing reads as nothing, a whole
float drops its fraction, a list or a mapping reads as compact JSON.
"""

from __future__ import annotations

import html
import json
import math
from collections.abc import Mapping, Sequence
from typing import Final, cast

__all__ = ["addslashes", "escape_html", "text_of"]

_TEXT_DIGITS: Final = 14
"""How many significant digits a float keeps when written as text."""

_JSON_EXPONENT_FROM: Final = 17
"""The digit count past which a float in JSON switches to an exponent."""

_PLAIN_POINT_FLOOR: Final = -3
"""The lowest decimal point position a float is still written plainly at: 0.0001."""

_SLASHED: Final = str.maketrans({"\\": "\\\\", "'": "\\'", '"': '\\"', "\0": "\\0"})


def text_of(value: object) -> str:
    """Return ``value`` as text: ``True`` is ``1``, ``False`` and ``None`` are empty.

    A float keeps 14 significant digits and drops a zero fraction; past them,
    or below a ten-thousandth, it takes an exponent, as in ``1.0E+20``.
    """
    match value:
        case str():
            return value
        case bool():
            return "1" if value else ""
        case None:
            return ""
        case float():
            return _float_text(value, _TEXT_DIGITS, "E")
        case _:
            return str(value)


def addslashes(text: str) -> str:
    """Return ``text`` with a backslash before each quote, backslash and NUL byte.

    So it fits between the double quotes of a Graphviz attribute.
    """
    return text.translate(_SLASHED)


def escape_html(value: object) -> str:
    """Return ``value`` as text fit for a Graphviz markup label.

    A flag reads ``1`` or ``0`` and ``None`` reads as nothing; a list or a
    mapping reads as compact JSON, slashes and non-ASCII letters left as they
    are, and as nothing when it holds a float JSON cannot write. The markup
    characters, both quotes included, become entities.
    """
    match value:
        case bool():
            return "1" if value else "0"
        case None:
            return ""
        case Mapping() | list() | tuple():
            try:
                text = _json_of(cast("object", value))
            except ValueError:
                text = ""
        case _:
            text = text_of(value)
    return html.escape(text, quote=True).replace("&#x27;", "&apos;")


def _json_of(value: object) -> str:
    """Return ``value`` as compact JSON.

    An empty mapping is an empty list, since nothing tells the two apart once
    written.

    Raises:
        ValueError: If ``value`` holds an infinite or not-a-number float.
    """
    if isinstance(value, Mapping):
        entries = cast("Mapping[object, object]", value).items()
        if not entries:
            return "[]"
        return "{" + ",".join(f"{_json_of(text_of(k))}:{_json_of(v)}" for k, v in entries) + "}"
    if isinstance(value, list | tuple):
        return "[" + ",".join(_json_of(item) for item in cast("Sequence[object]", value)) + "]"
    return _json_scalar_of(value)


def _json_scalar_of(value: object) -> str:
    """Return ``value``, neither a list nor a mapping, as JSON; any other object as its string.

    A line or paragraph separator stays escaped, as it ends a line in some readers.

    Raises:
        ValueError: If ``value`` is an infinite or not-a-number float.
    """
    match value:
        case bool():
            return "true" if value else "false"
        case None:
            return "null"
        case str():
            encoded = json.dumps(value, ensure_ascii=False)
            return encoded.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
        case float():
            if not math.isfinite(value):
                raise ValueError("JSON cannot hold an infinite or not-a-number float.")
            return _float_text(value, None, "e")
        case int():
            return str(value)
        case _:
            return _json_scalar_of(str(value))


def _float_text(value: float, digits: int | None, exponent_marker: str) -> str:
    """Return ``value`` with ``digits`` significant digits, or as few as read it back.

    Written plainly unless its decimal point sits more than three places before
    its first digit, or past the digits kept (17 when keeping as few as read
    it back), where it takes an exponent with at least one fractional digit.
    """
    if not math.isfinite(value):
        return "NAN" if math.isnan(value) else ("INF" if value > 0 else "-INF")
    sign = "-" if math.copysign(1.0, value) < 0 else ""
    if value == 0:
        return f"{sign}0"
    number = repr(abs(value)) if digits is None else format(abs(value), f".{digits - 1}e")
    figures, point = _figures_of(number)
    return sign + _laid_out(figures, point, digits or _JSON_EXPONENT_FROM, exponent_marker)


def _laid_out(figures: str, point: int, plain_up_to: int, exponent_marker: str) -> str:
    """Return ``figures`` with their decimal point at ``point``, plainly or with an exponent.

    Plainly while the point sits from three places before the first figure
    up to ``plain_up_to`` places after it.
    """
    if point < _PLAIN_POINT_FLOOR or point > plain_up_to:
        exponent = point - 1
        mantissa = f"{figures[0]}.{figures[1:] or '0'}"
        return f"{mantissa}{exponent_marker}{'+' if exponent >= 0 else '-'}{abs(exponent)}"
    if point <= 0:
        return f"0.{'0' * -point}{figures}"
    if point >= len(figures):
        return figures + "0" * (point - len(figures))
    return f"{figures[:point]}.{figures[point:]}"


def _figures_of(number: str) -> tuple[str, int]:
    """Return the significant figures of a positive ``number`` and where its decimal point falls.

    The point is counted from the first figure: 1 for ``1.5``, 0 for
    ``0.15``, -1 for ``0.015``.
    """
    mantissa, _, exponent = number.partition("e")
    whole, _, fraction = mantissa.partition(".")
    figures = whole + fraction
    significant = figures.lstrip("0")
    point = len(whole) + int(exponent or "0") - (len(figures) - len(significant))
    return significant.rstrip("0"), point
