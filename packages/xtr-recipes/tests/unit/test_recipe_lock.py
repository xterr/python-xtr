from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_recipes.recipe_lock import LockedFile, LockEntry, RecipeLock

if TYPE_CHECKING:
    from pathlib import Path

_EXPECTED_LOCK = """\
{
  "xtr-messenger": {
    "bundles": {
      "m.b:B": "listed"
    },
    "env": [
      "E"
    ],
    "files": {
      "src/app/x.py": {
        "adopted": false,
        "sha256": "s"
      }
    },
    "gitignore": [],
    "recipe": "h"
  }
}
"""


def test_a_missing_file_is_an_empty_lock(tmp_path: Path) -> None:
    assert RecipeLock.load(tmp_path) == RecipeLock({})


def test_a_non_object_lock_is_empty(tmp_path: Path) -> None:
    _ = (tmp_path / "xtr.lock").write_text("[]", encoding="utf-8")

    assert RecipeLock.load(tmp_path) == RecipeLock({})


def test_lock_entry_defaults_are_empty() -> None:
    entry = LockEntry()

    assert entry.recipe == ""
    assert entry.bundles == {}
    assert entry.files == {}
    assert entry.env == ()
    assert entry.gitignore == ()


def test_it_round_trips(tmp_path: Path) -> None:
    lock = RecipeLock(
        {
            "xtr-messenger": LockEntry(
                recipe="abc",
                bundles={"xtr_messenger.bundle:MessengerBundle": "listed"},
                files={"src/app/config/messenger.py": LockedFile(sha256="def", adopted=True)},
                env=("MESSENGER_DSN",),
                gitignore=("/var/messages",),
            ),
        },
    )

    lock.write(tmp_path)

    assert RecipeLock.load(tmp_path) == lock


def test_it_tolerates_a_non_object_entry(tmp_path: Path) -> None:
    _ = (tmp_path / "xtr.lock").write_text('{"p": "x"}', encoding="utf-8")

    assert RecipeLock.load(tmp_path).entries["p"] == LockEntry()


def test_it_tolerates_malformed_entry_fields(tmp_path: Path) -> None:
    _ = (tmp_path / "xtr.lock").write_text(
        '{"p": {"recipe": 5, "bundles": "x", "files": "y", "env": "z", "gitignore": 9}}',
        encoding="utf-8",
    )

    entry = RecipeLock.load(tmp_path).entries["p"]

    assert entry == LockEntry()


def test_it_drops_unrecognised_bundle_states(tmp_path: Path) -> None:
    _ = (tmp_path / "xtr.lock").write_text('{"p": {"bundles": {"m:B": "weird"}}}', encoding="utf-8")

    assert RecipeLock.load(tmp_path).entries["p"].bundles == {}


def test_it_skips_a_file_entry_that_is_not_an_object(tmp_path: Path) -> None:
    _ = (tmp_path / "xtr.lock").write_text('{"p": {"files": {"a.py": "nope"}}}', encoding="utf-8")

    assert RecipeLock.load(tmp_path).entries["p"].files == {}


def test_it_keeps_only_string_env_entries(tmp_path: Path) -> None:
    _ = (tmp_path / "xtr.lock").write_text('{"p": {"env": ["A", 2, "B"]}}', encoding="utf-8")

    assert RecipeLock.load(tmp_path).entries["p"].env == ("A", "B")


def test_it_writes_sorted_two_space_json_with_a_trailing_newline(tmp_path: Path) -> None:
    lock = RecipeLock(
        {
            "xtr-messenger": LockEntry(
                recipe="h",
                bundles={"m.b:B": "listed"},
                files={"src/app/x.py": LockedFile(sha256="s", adopted=False)},
                env=("E",),
                gitignore=(),
            ),
        },
    )

    lock.write(tmp_path)

    assert (tmp_path / "xtr.lock").read_text(encoding="utf-8") == _EXPECTED_LOCK


def test_dumps_returns_exactly_what_write_writes(tmp_path: Path) -> None:
    lock = RecipeLock({"xtr-messenger": LockEntry(recipe="h")})

    lock.write(tmp_path)

    assert lock.dumps() == (tmp_path / "xtr.lock").read_text(encoding="utf-8")


def test_an_empty_lock_dumps_an_empty_object() -> None:
    assert RecipeLock().dumps() == "{}\n"


def test_two_locks_recording_the_same_thing_dump_the_same_text() -> None:
    first = RecipeLock({"b-pkg": LockEntry(recipe="h"), "a-pkg": LockEntry(recipe="g")})
    second = RecipeLock({"a-pkg": LockEntry(recipe="g"), "b-pkg": LockEntry(recipe="h")})

    assert first.dumps() == second.dumps()
