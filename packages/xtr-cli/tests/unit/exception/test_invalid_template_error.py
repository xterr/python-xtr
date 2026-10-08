from __future__ import annotations

from xtr_cli.exception import InvalidTemplateError


def test_it_names_the_template_and_the_reason() -> None:
    error = InvalidTemplateError("mine", "summary must be a string")

    assert str(error) == "template 'mine': summary must be a string"
