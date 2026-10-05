from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_recipes.operation.bundle_note import BundleNote
from xtr_recipes.operation.keep_file import KeepFile
from xtr_recipes.operation.plan import Plan
from xtr_recipes.operation.section import Section
from xtr_recipes.operation.write_file import WriteFile

if TYPE_CHECKING:
    from pathlib import Path


def test_it_renders_every_step_in_order(tmp_path: Path) -> None:
    plan = Plan(
        (
            Section("configure", "xtr-messenger"),
            WriteFile(tmp_path / "config.py", "config.py", "BODY\n"),
            BundleNote("MessengerBundle", "listed"),
        )
    )

    assert plan.render() == (
        "configure xtr-messenger",
        "  write config.py",
        "  bundle MessengerBundle listed",
    )


def test_an_empty_plan_renders_nothing() -> None:
    assert Plan().render() == ()


def test_it_has_changes_when_a_step_writes(tmp_path: Path) -> None:
    plan = Plan((Section("configure", "x"), WriteFile(tmp_path / "a", "a", "")))

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
        (
            WriteFile(tmp_path / "first.py", "first.py", "ONE\n"),
            WriteFile(tmp_path / "second.py", "second.py", "TWO\n"),
        )
    )

    plan.apply()

    assert (tmp_path / "first.py").read_text(encoding="utf-8") == "ONE\n"
    assert (tmp_path / "second.py").read_text(encoding="utf-8") == "TWO\n"


def test_rendering_a_plan_writes_nothing(tmp_path: Path) -> None:
    _ = Plan((WriteFile(tmp_path / "config.py", "config.py", "BODY\n"),)).render()

    assert list(tmp_path.iterdir()) == []
