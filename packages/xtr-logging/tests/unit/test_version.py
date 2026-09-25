from __future__ import annotations

import tomllib
from pathlib import Path

import msgspec

import xtr_logging


def test_the_version_is_the_one_pyproject_declares() -> None:
    pyproject = Path(__file__).parents[2] / "pyproject.toml"
    project = msgspec.convert(tomllib.loads(pyproject.read_text())["project"], dict[str, object])

    assert xtr_logging.__version__ == project["version"]
