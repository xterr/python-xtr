from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, final

import pytest

from xtr_recipes.operation.bundle_note import BundleNote
from xtr_recipes.operation.delete_project_file import DeleteProjectFile
from xtr_recipes.operation.keep_file import KeepFile
from xtr_recipes.operation.plan import Plan
from xtr_recipes.operation.section import Section
from xtr_recipes.operation.write_file import WriteFile
from xtr_recipes.operation.write_lock import WriteLock
from xtr_recipes.recipe_lock import LockEntry, RecipeLock

if TYPE_CHECKING:
    from pathlib import Path

    from xtr_recipes.operation.operation_interface import OperationInterface


def test_it_renders_every_step_in_order(tmp_path: Path) -> None:
    plan = Plan(
        operations=(
            Section("configure", "xtr-messenger"),
            WriteFile(tmp_path / "config.py", "config.py", "BODY\n"),
            BundleNote("MessengerBundle", "listed"),
        ),
        project_operations=(DeleteProjectFile(tmp_path / "xtr.lock", "xtr.lock"),),
    )

    assert plan.render() == (
        "configure xtr-messenger",
        "  write config.py",
        "  bundle MessengerBundle listed",
        "delete xtr.lock",
    )


def test_an_empty_plan_renders_nothing() -> None:
    assert Plan().render() == ()


def test_it_has_changes_when_a_step_writes(tmp_path: Path) -> None:
    plan = Plan((Section("configure", "x"), WriteFile(tmp_path / "a", "a", "")))

    assert plan.has_changes


def test_it_has_changes_when_only_a_whole_project_step_writes(tmp_path: Path) -> None:
    plan = Plan(project_operations=(DeleteProjectFile(tmp_path / "xtr.lock", "xtr.lock"),))

    assert plan.has_changes


def test_a_plan_of_messages_only_has_no_changes() -> None:
    plan = Plan(
        (
            Section("unconfigure", "xtr-messenger"),
            KeepFile("src/app/config/messenger.py", "edited"),
            BundleNote("MessengerBundle", "removed"),
        )
    )

    assert not plan.has_changes


def test_an_empty_plan_has_no_changes() -> None:
    assert not Plan().has_changes


def test_it_applies_every_step(tmp_path: Path) -> None:
    plan = Plan(
        operations=(
            WriteFile(tmp_path / "first.py", "first.py", "ONE\n"),
            WriteFile(tmp_path / "second.py", "second.py", "TWO\n"),
        ),
        project_operations=(WriteLock(RecipeLock({"p": LockEntry(recipe="h")}), tmp_path),),
    )

    plan.apply()

    assert (tmp_path / "first.py").read_text(encoding="utf-8") == "ONE\n"
    assert (tmp_path / "second.py").read_text(encoding="utf-8") == "TWO\n"
    assert RecipeLock.load(tmp_path).entries == {"p": LockEntry(recipe="h")}


def test_rendering_a_plan_writes_nothing(tmp_path: Path) -> None:
    _ = Plan((WriteFile(tmp_path / "config.py", "config.py", "BODY\n"),)).render()

    assert list(tmp_path.iterdir()) == []


@final
class _Boom:
    changes: ClassVar[bool] = True

    def render(self) -> tuple[str, ...]:
        return ()

    def apply(self) -> None:
        raise RuntimeError("boom")


_CLOCK = "xtr-clock"
_MESSENGER = "xtr-messenger"
_BEFORE = RecipeLock(
    {_CLOCK: LockEntry(recipe="old-clock"), _MESSENGER: LockEntry(recipe="old-messenger")}
)
_AFTER = RecipeLock(
    {_CLOCK: LockEntry(recipe="new-clock"), _MESSENGER: LockEntry(recipe="new-messenger")}
)


def _two_packages(tmp_path: Path) -> tuple[OperationInterface, ...]:
    """Two blocks, the first writing a file whole and the second stopping in it."""
    return (
        Section("update", _CLOCK),
        WriteFile(tmp_path / "clock.py", "clock.py", "ONE\n"),
        Section("update", _MESSENGER),
        WriteFile(tmp_path / "messenger.py", "messenger.py", "TWO\n"),
        _Boom(),
    )


def test_a_failure_locks_the_package_that_finished_and_keeps_the_other_as_it_was(
    tmp_path: Path,
) -> None:
    plan = Plan(
        operations=_two_packages(tmp_path),
        project_operations=(WriteLock(_AFTER, tmp_path),),
        previous_lock=_BEFORE,
    )

    with pytest.raises(RuntimeError):
        plan.apply()

    assert RecipeLock.load(tmp_path).entries == {
        _CLOCK: LockEntry(recipe="new-clock"),
        _MESSENGER: LockEntry(recipe="old-messenger"),
    }


def test_a_package_that_stopped_part_way_and_was_never_locked_is_left_out(
    tmp_path: Path,
) -> None:
    plan = Plan(
        operations=_two_packages(tmp_path),
        project_operations=(WriteLock(_AFTER, tmp_path),),
    )

    with pytest.raises(RuntimeError):
        plan.apply()

    assert RecipeLock.load(tmp_path).entries == {_CLOCK: LockEntry(recipe="new-clock")}


def test_a_failure_in_the_whole_project_steps_records_nothing(tmp_path: Path) -> None:
    plan = Plan(
        operations=(
            Section("update", _CLOCK),
            WriteFile(tmp_path / "clock.py", "clock.py", "ONE\n"),
        ),
        project_operations=(_Boom(), WriteLock(_AFTER, tmp_path)),
        previous_lock=_BEFORE,
    )

    with pytest.raises(RuntimeError):
        plan.apply()

    assert not (tmp_path / "xtr.lock").exists()


def test_a_lock_it_cannot_write_does_not_stand_in_for_the_failure(tmp_path: Path) -> None:
    blocked = tmp_path / "blocked"
    _ = blocked.write_text("not a directory\n", encoding="utf-8")
    plan = Plan(
        operations=_two_packages(tmp_path),
        project_operations=(WriteLock(_AFTER, blocked),),
        previous_lock=_BEFORE,
    )

    with pytest.raises(RuntimeError, match="boom") as failure:
        plan.apply()

    assert failure.value.__notes__


def test_a_plan_with_no_lock_step_has_nothing_to_record(tmp_path: Path) -> None:
    plan = Plan(operations=_two_packages(tmp_path), previous_lock=_BEFORE)

    with pytest.raises(RuntimeError):
        plan.apply()

    assert not (tmp_path / "xtr.lock").exists()
