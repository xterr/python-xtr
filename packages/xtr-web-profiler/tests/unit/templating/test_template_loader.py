from __future__ import annotations

import pytest
from jinja2 import Environment, TemplateNotFound

from xtr_web_profiler.templating import TemplateLoader


@pytest.fixture
def environment() -> Environment:
    return Environment(loader=TemplateLoader(), autoescape=True)


def test_a_packages_template_is_found_by_its_import_name(environment: Environment) -> None:
    template = environment.get_template("@xtr_web_profiler/profiler/toolbar_item.html.j2")

    assert template.filename is not None
    assert template.filename.endswith("templates/profiler/toolbar_item.html.j2")
    assert template.is_up_to_date


@pytest.mark.parametrize(
    "name",
    [
        "profiler/toolbar.html.j2",
        "@xtr_web_profiler",
        "@/profiler/toolbar.html.j2",
        "@xtr_web_profiler/../pyproject.toml",
        "@xtr_web_profiler/profiler/missing.html.j2",
        "@no_such_package_here/a.html.j2",
    ],
    ids=["no-package", "no-path", "empty-package", "climbing", "missing", "not-installed"],
)
def test_a_name_that_names_no_package_template_is_not_found(
    environment: Environment, name: str
) -> None:
    with pytest.raises(TemplateNotFound):
        _ = environment.get_template(name)
