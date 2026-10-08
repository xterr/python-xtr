from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest
from xtr_console import ConsoleStyle

from xtr_cli import AddOnCatalog, ProjectQuestions, TemplateCatalog, UnknownAddOnError


def _questions(*answers: str, interactive: bool = True) -> tuple[ProjectQuestions, StringIO]:
    output = StringIO()
    io = ConsoleStyle(
        output,
        output,
        width=200,
        decorated=False,
        input_stream=StringIO("".join(f"{answer}\n" for answer in answers)),
        interactive=interactive,
    )
    return ProjectQuestions(io, TemplateCatalog.default(), AddOnCatalog.default()), output


def test_what_was_given_is_never_asked() -> None:
    questions, output = _questions()

    assert questions.directory(Path("shop")) == Path("shop")
    assert questions.template("webapp") == "webapp"
    assert [choice.variants for choice in questions.add_ons("orm", "cli")] == [("sqlite",)]
    assert output.getvalue() == ""


def test_with_no_interaction_the_defaults_are_taken_unasked() -> None:
    questions, _ = _questions(interactive=False)

    assert questions.directory(None) is None
    assert questions.template(None) == "cli"
    assert questions.add_ons(None, "cli") == ()
    assert questions.confirm()


def test_the_directory_and_template_are_asked_when_left_out() -> None:
    questions, output = _questions("shop", "webapp")

    assert questions.directory(None) == Path("shop")
    assert questions.template(None) == "webapp"
    assert "webapp — A web application" in output.getvalue()


def test_an_unanswered_template_question_takes_cli() -> None:
    questions, _ = _questions("")

    assert questions.template(None) == "cli"


def test_variants_are_asked_for_an_add_on_named_alone() -> None:
    questions, _ = _questions("orm, lock:redis", "postgres")

    chosen = questions.add_ons(None, "cli")

    assert [choice.spelling for choice in chosen] == ["orm:postgres", "lock:redis"]


def test_variants_spelled_out_in_the_answer_are_not_asked_again() -> None:
    questions, _ = _questions("orm:postgres, scheduler")

    chosen = questions.add_ons(None, "cli")

    assert [choice.spelling for choice in chosen] == ["orm:postgres", "scheduler"]


def test_a_wrong_answer_is_reported_and_asked_again() -> None:
    questions, output = _questions("queue", "orm", "oracle", "")

    chosen = questions.add_ons(None, "cli")

    assert [choice.variants for choice in chosen] == [("sqlite",)]
    assert "cannot add 'queue'" in output.getvalue()
    assert "oracle is not one of its database drivers" in output.getvalue()


def test_a_wrong_add_on_given_on_the_command_line_is_raised() -> None:
    questions, _ = _questions()

    with pytest.raises(UnknownAddOnError):
        _ = questions.add_ons("queue", "cli")


def test_going_ahead_can_be_declined() -> None:
    questions, _ = _questions("n")

    assert not questions.confirm()
