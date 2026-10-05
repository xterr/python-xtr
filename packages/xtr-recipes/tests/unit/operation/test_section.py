from __future__ import annotations

from xtr_recipes.operation.section import Section


def test_it_renders_the_action_and_the_package() -> None:
    assert Section("configure", "xtr-messenger").render() == ("configure xtr-messenger",)


def test_it_is_not_indented() -> None:
    (line,) = Section("unconfigure", "xtr-clock").render()

    assert not line.startswith(" ")


def test_it_changes_nothing() -> None:
    assert Section.changes is False


def test_applying_it_leaves_the_project_alone() -> None:
    assert Section("skip", "xtr-orm").apply() is None
