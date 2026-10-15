from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support import write_template
from xtr_cli import InvalidTemplateError, Template

if TYPE_CHECKING:
    from pathlib import Path

_VALUES = {"name": "web-shop", "app": "web_shop", "python": "3.13", "minor": "13"}

_MANIFEST = """\
summary = "A test template."

[dependencies]
packages = ["xtr-console"]
dev = ["pytest"]

[files]
"src/${app}/__main__.py" = "files/main.py.tmpl"

[notes]
next = ["uv run ${name}"]
"""


def _load(directory: Path, manifest: str = _MANIFEST, body: str = "APP = '${app}'\n") -> Template:
    return Template.load(write_template(directory, manifest, {"files/main.py.tmpl": body}), "t")


def test_a_template_is_read_from_its_manifest(tmp_path: Path) -> None:
    template = _load(tmp_path)

    assert template.summary == "A test template."
    assert template.dependencies == ("xtr-console",)
    assert template.dev_dependencies == ("pytest",)
    assert template.next_steps == ("uv run ${name}",)


def test_rendering_fills_the_destination_and_the_file(tmp_path: Path) -> None:
    assert _load(tmp_path).render(_VALUES) == (("src/web_shop/__main__.py", "APP = 'web_shop'\n"),)


def test_the_next_steps_are_filled_in(tmp_path: Path) -> None:
    assert _load(tmp_path).steps(_VALUES) == ("uv run web-shop",)


def test_a_doubled_dollar_is_a_literal_one(tmp_path: Path) -> None:
    assert _load(tmp_path, body="PRICE = '$$5'\n").render(_VALUES)[0][1] == "PRICE = '$5'\n"


def test_an_unknown_placeholder_is_refused(tmp_path: Path) -> None:
    template = _load(tmp_path, body="${nope}\n")

    with pytest.raises(InvalidTemplateError, match="unknown placeholder 'nope'"):
        _ = template.render(_VALUES)


def test_a_malformed_placeholder_is_refused(tmp_path: Path) -> None:
    template = _load(tmp_path, body="$\n")

    with pytest.raises(InvalidTemplateError, match="Invalid placeholder"):
        _ = template.render(_VALUES)


@pytest.mark.parametrize("destination", ["../outside.py", "/etc/passwd"])
def test_a_destination_outside_the_project_is_refused(tmp_path: Path, destination: str) -> None:
    manifest = f'[files]\n"{destination}" = "files/main.py.tmpl"\n'

    with pytest.raises(InvalidTemplateError, match="leaves the project"):
        _ = _load(tmp_path, manifest).render(_VALUES)


@pytest.mark.parametrize(
    ("manifest", "reason"),
    [
        ("summary = [", "cannot be read"),
        ("[extra]\n", "unknown key 'extra' in the manifest"),
        ("summary = 1\n", "summary must be a string"),
        ("dependencies = 1\n", "dependencies must be a table"),
        ("[dependencies]\nmain = []\n", r"unknown key 'main' in \[dependencies\]"),
        ("[dependencies]\npackages = [1]\n", "dependencies.packages must be a list of strings"),
        ("[notes]\nnext = 'x'\n", "notes.next must be a list of strings"),
        ("files = 1\n", "files must be a table"),
        ('[files]\n"a.py" = 1\n', "must name a file"),
        ('[files]\n"a.py" = "files/missing.tmpl"\n', "no file 'files/missing.tmpl'"),
        ('[files]\n"a.py" = "../template.toml"\n', "no file '../template.toml'"),
    ],
)
def test_a_manifest_it_cannot_read_names_what_is_wrong(
    tmp_path: Path, manifest: str, reason: str
) -> None:
    with pytest.raises(InvalidTemplateError, match=reason):
        _ = _load(tmp_path / "template", manifest)


def test_a_missing_manifest_cannot_be_read(tmp_path: Path) -> None:
    with pytest.raises(InvalidTemplateError, match="cannot be read"):
        _ = Template.load(tmp_path, "t")
