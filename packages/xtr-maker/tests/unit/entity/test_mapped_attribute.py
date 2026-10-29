"""Unit tests for :class:`xtr_maker.entity.MappedAttribute`.

The expected strings are what the formatter writes at its default line length.
"""

from __future__ import annotations

from xtr_maker.entity import MappedAttribute


def test_a_short_attribute_is_one_line() -> None:
    attribute = MappedAttribute("title", "str", "mapped_column", ("String(120)",))

    assert attribute.render() == "title: Mapped[str] = mapped_column(String(120))\n"


def test_a_long_attribute_puts_its_arguments_on_a_line_of_their_own() -> None:
    attribute = MappedAttribute(
        "published_at",
        "datetime | None",
        "mapped_column",
        ("DateTimeUTC(timezone=True)", "nullable=True"),
    )

    assert attribute.render() == (
        "published_at: Mapped[datetime | None] = mapped_column(\n"
        "    DateTimeUTC(timezone=True), nullable=True\n"
        ")\n"
    )


def test_arguments_too_long_for_one_line_go_one_per_line() -> None:
    attribute = MappedAttribute(
        "author",
        "Author",
        "relationship",
        ('back_populates="books_written_by_this_author"', 'foreign_keys="[Book.author_id]"'),
    )

    assert attribute.render(line_length=60) == (
        "author: Mapped[Author] = relationship(\n"
        '    back_populates="books_written_by_this_author",\n'
        '    foreign_keys="[Book.author_id]",\n'
        ")\n"
    )


def test_no_arguments_leave_the_call_empty() -> None:
    assert MappedAttribute("tags", "list[Tag]", "relationship").render() == (
        "tags: Mapped[list[Tag]] = relationship()\n"
    )
