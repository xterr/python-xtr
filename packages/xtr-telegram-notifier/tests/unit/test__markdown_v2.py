from __future__ import annotations

import pytest

from xtr_telegram_notifier._markdown_v2 import escape_markdown_v2


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        pytest.param(
            "Hello world. Cost: 10 EUR!", "Hello world\\. Cost: 10 EUR\\!", id="plain text"
        ),
        pytest.param(
            "v1.2.3 at 10:30, a/b; x<y",
            "v1\\.2\\.3 at 10:30, a/b; x<y",
            id="digits and unreserved punctuation",
        ),
        pytest.param("Version 1\\.2 and \\\\.", "Version 1\\.2 and \\\\\\.", id="already escaped"),
        pytest.param(
            "*bold* _italic_ __underline__ `code` ~strike~ ||spoiler|| [link](https://example.com/)",
            "*bold* _italic_ __underline__ `code` ~strike~ ||spoiler|| [link](https://example\\.com/)",
            id="paired markup",
        ),
        pytest.param(
            ">Quote\n>More\n**>Expandable\n>Last line||",
            ">Quote\n>More\n**>Expandable\n>Last line||",
            id="block quotation",
        ),
        pytest.param(
            "a > b, a | b, a ! b, **> c",
            "a \\> b, a \\| b, a \\! b, **\\> c",
            id="reserved characters outside markup",
        ),
        pytest.param(
            "![👍](tg://emoji?id=5368324170671202286)",
            "![👍](tg://emoji?id\\=5368324170671202286)",
            id="custom emoji",
        ),
        pytest.param("", "", id="empty"),
    ],
)
def test_it_escapes_reserved_characters_but_not_markup(subject: str, expected: str) -> None:
    assert escape_markdown_v2(subject) == expected
