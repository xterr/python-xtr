from __future__ import annotations

from tests.support.records import make_record
from xtr_logging.processor.tag_processor import TagProcessor


def test_it_adds_the_tags_it_was_built_with() -> None:
    processor = TagProcessor(["billing", "eu"])

    record = processor(make_record())

    assert record.extra["tags"] == ["billing", "eu"]


def test_tags_default_to_empty() -> None:
    record = TagProcessor()(make_record())

    assert record.extra["tags"] == []


def test_add_tags_appends_to_the_existing_ones() -> None:
    processor = TagProcessor(["a"])

    processor.add_tags("b", "c")

    assert processor(make_record()).extra["tags"] == ["a", "b", "c"]


def test_set_tags_replaces_them() -> None:
    processor = TagProcessor(["a"])

    processor.set_tags(["x", "y"])

    assert processor(make_record()).extra["tags"] == ["x", "y"]
