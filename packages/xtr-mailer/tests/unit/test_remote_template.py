"""The reference and variables of a template a mail provider renders."""

from __future__ import annotations

from xtr_mailer import RemoteTemplate


def test_the_reference_is_kept() -> None:
    assert RemoteTemplate("welcome").get_reference() == "welcome"


def test_the_variables_default_to_empty() -> None:
    assert RemoteTemplate("welcome").get_variables() == {}


def test_the_variables_are_kept() -> None:
    template = RemoteTemplate("welcome", {"firstName": "Fabien", "count": 3})

    assert template.get_variables() == {"firstName": "Fabien", "count": 3}


def test_the_variables_are_copied_in() -> None:
    variables: dict[str, object] = {"firstName": "Fabien"}
    template = RemoteTemplate("welcome", variables)

    variables["firstName"] = "Hélène"

    assert template.get_variables() == {"firstName": "Fabien"}


def test_changing_the_returned_variables_leaves_the_template_alone() -> None:
    template = RemoteTemplate("welcome", {"firstName": "Fabien"})

    template.get_variables()["firstName"] = "Hélène"

    assert template.get_variables() == {"firstName": "Fabien"}


def test_the_representation_shows_the_reference_and_the_variable_names_only() -> None:
    template = RemoteTemplate("welcome", {"firstName": "Fabien", "count": 3})

    assert repr(template) == "RemoteTemplate('welcome', variables=['firstName', 'count'])"
