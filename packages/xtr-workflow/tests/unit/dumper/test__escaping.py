"""The dumpers write values as text the way the diagrams they reproduce were first written."""

from __future__ import annotations

import math
from decimal import Decimal

import pytest
from typing_extensions import override

from xtr_workflow.dumper._escaping import addslashes, escape_html, text_of


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param("plain", "plain", id="text"),
        pytest.param(True, "1", id="true"),
        pytest.param(False, "", id="false"),
        pytest.param(None, "", id="none"),
        pytest.param(42, "42", id="int"),
        pytest.param(1.5, "1.5", id="float"),
        pytest.param(-2.5, "-2.5", id="negative-float"),
        pytest.param(2.0, "2", id="whole-float"),
        pytest.param(100.0, "100", id="whole-float-with-zeros"),
        pytest.param(0.0, "0", id="zero"),
        pytest.param(-0.0, "-0", id="negative-zero"),
        pytest.param(0.1, "0.1", id="fraction"),
        pytest.param(0.0001, "0.0001", id="small-fraction"),
        pytest.param(0.1 + 0.2, "0.3", id="fourteen-digits"),
        pytest.param(1e-5, "1.0E-5", id="tiny"),
        pytest.param(1e14, "1.0E+14", id="large"),
        pytest.param(1e20, "1.0E+20", id="huge"),
        pytest.param(1.5e300, "1.5E+300", id="huge-with-fraction"),
        pytest.param(123456789012345.6, "1.2345678901235E+14", id="rounded"),
        pytest.param(math.inf, "INF", id="infinity"),
        pytest.param(-math.inf, "-INF", id="negative-infinity"),
        pytest.param(math.nan, "NAN", id="not-a-number"),
    ],
)
def test_text_of_writes_a_value_as_text(value: object, expected: str) -> None:
    assert text_of(value) == expected


def test_text_of_writes_any_other_object_as_its_string() -> None:
    class Named:
        @override
        def __str__(self) -> str:
            return "named"

    assert text_of(Named()) == "named"


def test_addslashes_escapes_quotes_backslashes_and_nul() -> None:
    assert addslashes("a\0b'\"\\c") == "a\\0b\\'\\\"\\\\c"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param(
            "<a href='x'>&amp;\"</a>",
            "&lt;a href=&apos;x&apos;&gt;&amp;amp;&quot;&lt;/a&gt;",
            id="markup",
        ),
        pytest.param("a\0b", "a\0b", id="nul-kept"),
        pytest.param(True, "1", id="true"),
        pytest.param(False, "0", id="false"),
        pytest.param(None, "", id="none"),
        pytest.param(42, "42", id="int"),
        pytest.param(2.0, "2", id="whole-float"),
        pytest.param(["x", "y"], "[&quot;x&quot;,&quot;y&quot;]", id="list"),
        pytest.param(("x",), "[&quot;x&quot;]", id="tuple"),
        pytest.param({"k": "v"}, "{&quot;k&quot;:&quot;v&quot;}", id="mapping"),
        pytest.param({}, "[]", id="empty-mapping"),
        pytest.param([], "[]", id="empty-list"),
        pytest.param({"e": {}}, "{&quot;e&quot;:[]}", id="nested-empty-mapping"),
        pytest.param(
            ["a/b", "é"], "[&quot;a/b&quot;,&quot;é&quot;]", id="slashes-and-unicode-unescaped"
        ),
        pytest.param(
            ["x\u2028y\u2029"], "[&quot;x\\u2028y\\u2029&quot;]", id="line-terminators-escaped"
        ),
        pytest.param(
            ['\x01\x1f\x7f\b\f\n\r\t"\\'],
            "[&quot;\\u0001\\u001f\x7f\\b\\f\\n\\r\\t\\&quot;\\\\&quot;]",
            id="control-characters",
        ),
        pytest.param([True, False, None], "[true,false,null]", id="literals"),
        pytest.param([0.0, -0.0, 2.0, 1.5], "[0,-0,2,1.5]", id="floats"),
        pytest.param(
            [1e16, 1e17, 1e-5, 0.0001],
            "[10000000000000000,1.0e+17,1.0e-5,0.0001]",
            id="float-notation",
        ),
        pytest.param(
            [0.1 + 0.2, 123456789012345678.0],
            "[0.30000000000000004,1.2345678901234568e+17]",
            id="shortest-digits",
        ),
        pytest.param([math.inf], "", id="not-encodable"),
        pytest.param([Decimal("1.5")], "[&quot;1.5&quot;]", id="other-object-as-its-string"),
    ],
)
def test_escape_html_writes_a_value_as_markup_text(value: object, expected: str) -> None:
    assert escape_html(value) == expected
