from __future__ import annotations

import tomllib
from pathlib import Path
from typing import cast

import xtr_logging_contracts


def test_the_version_is_the_one_pyproject_declares() -> None:
    pyproject = Path(__file__).parents[2] / "pyproject.toml"
    data = cast(
        "dict[str, dict[str, object]]",
        tomllib.loads(pyproject.read_text(encoding="utf-8")),
    )

    assert xtr_logging_contracts.__version__ == data["project"]["version"]
