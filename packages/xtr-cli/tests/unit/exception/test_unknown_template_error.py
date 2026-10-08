from __future__ import annotations

from xtr_cli.exception import UnknownTemplateError


def test_it_names_the_shipped_templates() -> None:
    error = UnknownTemplateError("nope", ("cli", "webapp"))

    assert "choose cli, webapp" in str(error)
