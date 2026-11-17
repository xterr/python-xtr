from __future__ import annotations

from typing import final

from xtr_http_kernel.data_collector import clone_var

from xtr_web_profiler.templating import dump


def test_a_plain_value_is_shown_as_itself_escaped() -> None:
    assert dump("<b>") == '<span class="xtr-dump-scalar" title="">&lt;b&gt;</span>'
    assert dump({"no": "kind"}) == (
        '<span class="xtr-dump-scalar" title="">{&#39;no&#39;: &#39;kind&#39;}</span>'
    )


def test_scalars_are_marked_by_kind() -> None:
    assert dump(clone_var(None)) == '<span class="xtr-dump-null">None</span>'
    assert dump(clone_var(value=True)) == '<span class="xtr-dump-bool">True</span>'
    assert dump(clone_var(3)) == '<span class="xtr-dump-number">3</span>'


def test_text_is_quoted_escaped_and_says_what_was_cut() -> None:
    html = dump(clone_var("<script>", max_string=3))

    assert html == (
        '<span class="xtr-dump-str" title="str">"&lt;sc"</span>'
        ' <span class="xtr-dump-more">… 5 more</span>'
    )


def test_bytes_show_their_length() -> None:
    assert "(2 bytes)" in dump(clone_var(b"ab"))


def test_containers_nest_and_open_on_the_first_level() -> None:
    html = dump(clone_var({"shelf": [1, 2]}))

    assert html.startswith('<details class="xtr-dump" open>')
    assert html.count("<details") == 2
    assert '<details class="xtr-dump">' in html


def test_an_object_lists_its_attributes() -> None:
    @final
    class Book:
        def __init__(self) -> None:
            self.title = "Dune"

    html = dump(clone_var(Book()))

    assert '<span class="xtr-dump-key">title</span>' in html


def test_a_cut_says_why() -> None:
    node: dict[str, object] = {}
    node["self"] = node

    assert "already shown above" in dump(clone_var(node))
    assert "too deep" in dump(clone_var([[1]], max_depth=1))


def test_a_long_container_says_how_many_items_were_left_out() -> None:
    assert "… 2 more" in dump(clone_var([1, 2, 3], max_items=1))
