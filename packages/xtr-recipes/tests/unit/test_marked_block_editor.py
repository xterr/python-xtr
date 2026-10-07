from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from xtr_recipes.exception import MarkedBlockError
from xtr_recipes.marked_block_editor import MarkedBlockEditor

if TYPE_CHECKING:
    from pathlib import Path

_PACKAGE = "xtr-messenger"
_BLOCK = """\
# >>> xtr-messenger
MESSENGER_DSN=amqp://localhost
# <<< xtr-messenger
"""


@pytest.fixture
def editor() -> MarkedBlockEditor:
    return MarkedBlockEditor()


def test_it_writes_a_key_the_file_lacks(editor: MarkedBlockEditor) -> None:
    assert editor.env_lines("OTHER=1\n", _PACKAGE, {"MESSENGER_DSN": "amqp://"}) == (
        "MESSENGER_DSN=amqp://",
    )


def test_it_skips_a_key_already_assigned(editor: MarkedBlockEditor) -> None:
    text = "MESSENGER_DSN=amqp://mine\n"

    assert editor.env_lines(text, _PACKAGE, {"MESSENGER_DSN": "amqp://"}) == ()


def test_it_skips_a_key_assigned_with_export(editor: MarkedBlockEditor) -> None:
    text = "export MESSENGER_DSN=amqp://mine\n"

    assert editor.env_lines(text, _PACKAGE, {"MESSENGER_DSN": "amqp://"}) == ()


def test_it_writes_a_key_that_is_only_commented_out(editor: MarkedBlockEditor) -> None:
    text = "# MESSENGER_DSN=\n"

    assert editor.env_lines(text, _PACKAGE, {"MESSENGER_DSN": "amqp://"}) == (
        "MESSENGER_DSN=amqp://",
    )


def test_it_keeps_the_value_set_inside_its_own_block(editor: MarkedBlockEditor) -> None:
    assert editor.env_lines(_BLOCK, _PACKAGE, {"MESSENGER_DSN": "amqp://"}) == (
        "MESSENGER_DSN=amqp://localhost",
    )


def test_it_comments_out_a_key_with_no_default(editor: MarkedBlockEditor) -> None:
    assert editor.env_lines("", _PACKAGE, {"MESSENGER_DSN": ""}) == ("# MESSENGER_DSN=",)


def test_it_does_not_mistake_a_longer_key_for_the_one_asked(editor: MarkedBlockEditor) -> None:
    text = "MESSENGER_DSN_EXTRA=1\n"

    assert editor.env_lines(text, _PACKAGE, {"MESSENGER_DSN": ""}) == ("# MESSENGER_DSN=",)


def test_env_keys_names_what_env_lines_would_write(editor: MarkedBlockEditor) -> None:
    entries = {"MESSENGER_DSN": "", "MESSENGER_RETRY": "3"}

    assert editor.env_keys("", _PACKAGE, entries) == ("MESSENGER_DSN", "MESSENGER_RETRY")


def test_env_keys_leaves_out_a_key_the_project_already_sets(editor: MarkedBlockEditor) -> None:
    text = "MESSENGER_DSN=amqp://mine\n"

    assert editor.env_keys(text, _PACKAGE, {"MESSENGER_DSN": "", "OTHER": ""}) == ("OTHER",)


def test_env_keys_counts_a_key_only_its_own_block_sets(editor: MarkedBlockEditor) -> None:
    assert editor.env_keys(_BLOCK, _PACKAGE, {"MESSENGER_DSN": ""}) == ("MESSENGER_DSN",)


def test_env_keys_and_env_lines_agree_on_how_many(editor: MarkedBlockEditor) -> None:
    text = "MESSENGER_DSN=amqp://mine\n"
    entries = {"MESSENGER_DSN": "", "MESSENGER_RETRY": "3"}

    assert len(editor.env_keys(text, _PACKAGE, entries)) == len(
        editor.env_lines(text, _PACKAGE, entries)
    )


def test_it_keeps_an_ignore_line_the_file_lacks(editor: MarkedBlockEditor) -> None:
    assert editor.ignore_lines("/build\n", _PACKAGE, ["/var/messages"]) == ("/var/messages",)


def test_it_skips_an_ignore_line_already_present(editor: MarkedBlockEditor) -> None:
    text = "  /var/messages  \n"

    assert editor.ignore_lines(text, _PACKAGE, ["/var/messages"]) == ()


def test_it_keeps_a_repeated_ignore_line_once(editor: MarkedBlockEditor) -> None:
    assert editor.ignore_lines("", _PACKAGE, ["/a", "/a"]) == ("/a",)


def test_it_drops_a_blank_ignore_line(editor: MarkedBlockEditor) -> None:
    assert editor.ignore_lines("", _PACKAGE, ["   "]) == ()


def test_it_appends_a_new_block_after_one_blank_line(editor: MarkedBlockEditor) -> None:
    result = editor.put_block("OTHER=1\n", _PACKAGE, ["MESSENGER_DSN=amqp://localhost"])

    assert result == f"OTHER=1\n\n{_BLOCK}"


def test_it_appends_to_text_without_a_trailing_newline(editor: MarkedBlockEditor) -> None:
    result = editor.put_block("OTHER=1", _PACKAGE, ["MESSENGER_DSN=amqp://localhost"])

    assert result == f"OTHER=1\n\n{_BLOCK}"


def test_it_writes_a_block_into_an_empty_file(editor: MarkedBlockEditor) -> None:
    assert editor.put_block("", _PACKAGE, ["MESSENGER_DSN=amqp://localhost"]) == _BLOCK


def test_it_replaces_an_existing_block_where_it_stands(editor: MarkedBlockEditor) -> None:
    text = f"{_BLOCK}\nOTHER=1\n"

    result = editor.put_block(text, _PACKAGE, ["MESSENGER_DSN=amqp://other"])

    assert result == (
        "# >>> xtr-messenger\nMESSENGER_DSN=amqp://other\n# <<< xtr-messenger\n\nOTHER=1\n"
    )


def test_it_leaves_another_packages_block_alone(editor: MarkedBlockEditor) -> None:
    text = "# >>> xtr-orm\nDATABASE_URL=\n# <<< xtr-orm\n"

    result = editor.put_block(text, _PACKAGE, ["MESSENGER_DSN=amqp://localhost"])

    assert result == f"{text}\n{_BLOCK}"


def test_putting_the_same_block_twice_changes_nothing(editor: MarkedBlockEditor) -> None:
    lines = ["MESSENGER_DSN=amqp://localhost"]
    once = editor.put_block("OTHER=1\n", _PACKAGE, lines)

    assert editor.put_block(once, _PACKAGE, lines) == once


def test_putting_no_lines_removes_the_block(editor: MarkedBlockEditor) -> None:
    assert editor.put_block(f"OTHER=1\n\n{_BLOCK}", _PACKAGE, []) == "OTHER=1\n"


def test_removing_a_block_takes_its_blank_separator_with_it(editor: MarkedBlockEditor) -> None:
    assert editor.remove_block(f"OTHER=1\n\n{_BLOCK}", _PACKAGE) == "OTHER=1\n"


def test_removing_a_leading_block_takes_the_blank_line_below_it(editor: MarkedBlockEditor) -> None:
    assert editor.remove_block(f"{_BLOCK}\nOTHER=1\n", _PACKAGE) == "OTHER=1\n"


def test_removing_the_only_block_empties_the_text(editor: MarkedBlockEditor) -> None:
    assert editor.remove_block(_BLOCK, _PACKAGE) == ""


def test_removing_an_absent_block_leaves_the_text_untouched(editor: MarkedBlockEditor) -> None:
    assert editor.remove_block("OTHER=1", _PACKAGE) == "OTHER=1"


def test_it_reads_the_lines_inside_a_block(editor: MarkedBlockEditor) -> None:
    assert editor.block_lines(f"OTHER=1\n\n{_BLOCK}", _PACKAGE) == (
        "MESSENGER_DSN=amqp://localhost",
    )


def test_it_reads_no_lines_without_a_block(editor: MarkedBlockEditor) -> None:
    assert editor.block_lines("OTHER=1\n", _PACKAGE) == ()


def test_an_unclosed_block_is_an_error(editor: MarkedBlockEditor) -> None:
    text = "# >>> xtr-messenger\nMESSENGER_DSN=\n"

    with pytest.raises(MarkedBlockError) as raised:
        _ = editor.block_lines(text, _PACKAGE)

    assert raised.value.path_or_name == _PACKAGE
    assert "# <<< xtr-messenger" in raised.value.reason


def test_it_reads_a_missing_file_as_empty(editor: MarkedBlockEditor, tmp_path: Path) -> None:
    assert editor.read(tmp_path / ".env") == ""


def test_it_writes_a_file_it_has_to_make_room_for(
    editor: MarkedBlockEditor, tmp_path: Path
) -> None:
    path = tmp_path / "nested" / ".env"

    editor.write(path, _BLOCK)

    assert editor.read(path) == _BLOCK


def test_it_creates_an_env_file_owner_only(editor: MarkedBlockEditor, tmp_path: Path) -> None:
    path = tmp_path / ".env"

    editor.write(path, _BLOCK)

    assert path.stat().st_mode & 0o777 == 0o600


def test_it_does_not_force_a_gitignore_to_owner_only(
    editor: MarkedBlockEditor, tmp_path: Path
) -> None:
    path = tmp_path / ".gitignore"

    editor.write(path, "/var/messenger\n")

    assert path.stat().st_mode & 0o200
