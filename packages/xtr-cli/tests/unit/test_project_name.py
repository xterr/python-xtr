from __future__ import annotations

import pytest

from xtr_cli import InvalidProjectNameError, ProjectName


@pytest.mark.parametrize(
    ("text", "distribution", "app"),
    [
        ("shop", "shop", "shop"),
        ("Web Shop", "web-shop", "web_shop"),
        ("web_shop", "web-shop", "web_shop"),
        ("--my..App--", "my-app", "my_app"),
    ],
)
def test_a_name_is_normalised_into_a_distribution_and_an_import_name(
    text: str, distribution: str, app: str
) -> None:
    assert ProjectName.parse(text) == ProjectName(distribution, app)


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("---", "no letter or digit"),
        ("1shop", "not a valid import name"),
        ("class", "keyword"),
        ("json", "standard library"),
    ],
)
def test_a_name_that_would_not_import_is_refused(text: str, reason: str) -> None:
    with pytest.raises(InvalidProjectNameError, match=reason) as raised:
        _ = ProjectName.parse(text)

    assert raised.value.name == text
