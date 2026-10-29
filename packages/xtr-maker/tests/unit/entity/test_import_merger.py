"""Unit tests for :class:`xtr_maker.entity.ImportMerger`.

The expected modules are what the linter's import sorting writes.
"""

from __future__ import annotations

import libcst as cst

from xtr_maker import ImportCollector
from xtr_maker.entity import ImportMerger

_MODULE = '''"""A module."""

from __future__ import annotations

from typing import final

from sqlalchemy.orm import Mapped

from app.entity.base import Base

__all__ = ["Thing"]
'''


def _merge(source: str, *imports: tuple[str, str, bool], line_length: int = 88) -> str:
    collector = ImportCollector("app")
    for module, name, type_checking in imports:
        _ = collector.add(module, name, type_checking=type_checking)
    merger = ImportMerger("app", line_length=line_length)
    return merger.merge(cst.parse_module(source), collector).code


def test_a_name_already_imported_changes_nothing() -> None:
    assert _merge(_MODULE, ("sqlalchemy.orm", "Mapped", False)) == _MODULE


def test_a_name_joins_the_statement_of_its_module_sorted() -> None:
    merged = _merge(_MODULE, ("sqlalchemy.orm", "mapped_column", False), ("typing", "Final", False))

    assert "from typing import Final, final\n" in merged
    assert "from sqlalchemy.orm import Mapped, mapped_column\n" in merged


def test_a_new_module_takes_its_place_in_its_section() -> None:
    merged = _merge(_MODULE, ("decimal", "Decimal", False), ("sqlalchemy", "String", False))

    assert merged == _MODULE.replace(
        "from typing import final\n",
        "from decimal import Decimal\nfrom typing import final\n",
    ).replace(
        "from sqlalchemy.orm import Mapped\n",
        "from sqlalchemy import String\nfrom sqlalchemy.orm import Mapped\n",
    )


def test_a_new_section_is_set_apart_by_blank_lines() -> None:
    source = '"""A module."""\n\nfrom __future__ import annotations\n\nfrom app.base import Base\n'

    merged = _merge(source, ("uuid", "UUID", False), ("sqlalchemy", "String", False))

    assert merged == (
        '"""A module."""\n\n'
        "from __future__ import annotations\n\n"
        "from uuid import UUID\n\n"
        "from sqlalchemy import String\n\n"
        "from app.base import Base\n"
    )


def test_a_module_with_only_a_docstring_gets_its_imports_after_it() -> None:
    merged = _merge('"""A module."""\nx = 1\n', ("uuid", "UUID", False))

    assert merged == '"""A module."""\n\nfrom uuid import UUID\n\nx = 1\n'


def test_a_name_for_annotations_goes_in_a_new_type_checking_block() -> None:
    merged = _merge(_MODULE, ("app.entity.author", "Author", True))

    assert merged == _MODULE.replace(
        "from typing import final\n", "from typing import TYPE_CHECKING, final\n"
    ).replace(
        '__all__ = ["Thing"]',
        'if TYPE_CHECKING:\n    from app.entity.author import Author\n\n__all__ = ["Thing"]',
    )


def test_a_name_for_annotations_joins_the_existing_type_checking_block() -> None:
    source = _MODULE.replace(
        '__all__ = ["Thing"]',
        "if TYPE_CHECKING:\n    from app.entity.book import Book\n\n__all__ = []",
    ).replace("from typing import final", "from typing import TYPE_CHECKING, final")

    merged = _merge(source, ("app.entity.author", "Author", True), ("decimal", "Decimal", True))

    assert (
        "if TYPE_CHECKING:\n"
        "    from decimal import Decimal\n\n"
        "    from app.entity.author import Author\n"
        "    from app.entity.book import Book\n\n"
    ) in merged


def test_a_name_imported_at_runtime_is_not_imported_again_for_annotations() -> None:
    assert _merge(_MODULE, ("app.entity.base", "Base", True)) == _MODULE


def test_a_statement_too_long_for_a_line_is_wrapped() -> None:
    merged = _merge(_MODULE, ("sqlalchemy.orm", "relationship", False), line_length=40)

    assert "from sqlalchemy.orm import (\n    Mapped,\n    relationship,\n)\n" in merged


def test_a_statement_with_a_comment_is_left_alone() -> None:
    source = _MODULE.replace("import Mapped\n", "import Mapped  # the annotation\n")

    merged = _merge(source, ("sqlalchemy.orm", "relationship", False))

    assert "from sqlalchemy.orm import Mapped  # the annotation\n" in merged
    assert "from sqlalchemy.orm import relationship\n" in merged


def test_a_plain_import_sorts_before_from_imports_of_its_section() -> None:
    source = '"""A module."""\n\nimport os\nfrom typing import final\n'

    merged = _merge(source, ("decimal", "Decimal", False))

    assert (
        merged
        == '"""A module."""\n\nimport os\nfrom decimal import Decimal\nfrom typing import final\n'
    )
