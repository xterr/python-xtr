from __future__ import annotations

import pytest

from xtr_recipes import ComposeFileEditor, MarkedBlockError

_ORM = "xtr-orm"
_DATABASE = ("  database:", "    image: postgres:16-alpine")
_VOLUME = ("  database_data:",)
_WRITTEN = """\
services:
###> xtr-orm ###
  database:
    image: postgres:16-alpine
###< xtr-orm ###

volumes:
###> xtr-orm ###
  database_data:
###< xtr-orm ###
"""


@pytest.fixture
def editor() -> ComposeFileEditor:
    return ComposeFileEditor()


def test_a_new_file_gets_each_key_with_the_package_block_under_it(
    editor: ComposeFileEditor,
) -> None:
    written = editor.put_blocks("", _ORM, {"services": _DATABASE, "volumes": _VOLUME})

    assert written == _WRITTEN


def test_putting_the_same_blocks_again_changes_nothing(editor: ComposeFileEditor) -> None:
    sections = {"services": _DATABASE, "volumes": _VOLUME}

    assert editor.put_blocks(_WRITTEN, _ORM, sections) == _WRITTEN


def test_a_block_goes_after_the_entries_already_under_its_key(editor: ComposeFileEditor) -> None:
    text = "services:\n  app:\n    image: app\n\nvolumes: {}\n"

    written = editor.put_blocks(text, _ORM, {"services": _DATABASE})

    assert written == (
        "services:\n  app:\n    image: app\n\n"
        "###> xtr-orm ###\n  database:\n    image: postgres:16-alpine\n###< xtr-orm ###\n\n"
        "volumes: {}\n"
    )


def test_a_block_is_rewritten_where_it_stands(editor: ComposeFileEditor) -> None:
    text = "services:\n###> xtr-orm ###\n  old:\n###< xtr-orm ###\n  app:\n    image: app\n"

    written = editor.put_blocks(text, _ORM, {"services": _DATABASE})

    assert written == (
        "services:\n###> xtr-orm ###\n  database:\n    image: postgres:16-alpine\n"
        "###< xtr-orm ###\n  app:\n    image: app\n"
    )


def test_a_block_takes_the_indentation_the_file_uses(editor: ComposeFileEditor) -> None:
    text = "services:\n    app:\n        image: app\n"

    written = editor.put_blocks(text, _ORM, {"services": _DATABASE})

    assert "    database:\n        image: postgres:16-alpine\n" in written


def test_another_packages_block_is_left_alone(editor: ComposeFileEditor) -> None:
    text = "services:\n###> xtr-mailer ###\n  mailer:\n###< xtr-mailer ###\n"

    written = editor.put_blocks(text, _ORM, {"services": _DATABASE})

    assert written.startswith(text)
    assert editor.put_blocks(written, _ORM, {}) == text


def test_no_sections_clears_the_blocks_and_the_keys_they_leave_empty(
    editor: ComposeFileEditor,
) -> None:
    text = f"{_WRITTEN}\nnetworks:\n  front:\n"

    assert editor.put_blocks(text, _ORM, {}) == "networks:\n  front:\n"


def test_clearing_every_block_of_a_file_leaves_nothing(editor: ComposeFileEditor) -> None:
    assert editor.put_blocks(_WRITTEN, _ORM, {}) == ""


def test_a_key_the_recipe_no_longer_writes_under_is_cleared(editor: ComposeFileEditor) -> None:
    written = editor.put_blocks(_WRITTEN, _ORM, {"services": _DATABASE})

    assert written == _WRITTEN.split("\nvolumes:", maxsplit=1)[0]


def test_it_tells_whether_the_package_has_blocks(editor: ComposeFileEditor) -> None:
    assert editor.has_blocks(_WRITTEN, _ORM)
    assert not editor.has_blocks("services:\n", _ORM)


def test_an_unclosed_block_is_refused(editor: ComposeFileEditor) -> None:
    with pytest.raises(MarkedBlockError):
        _ = editor.put_blocks("services:\n###> xtr-orm ###\n  database:\n", _ORM, {})
