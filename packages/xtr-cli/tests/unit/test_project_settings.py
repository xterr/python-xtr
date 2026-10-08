from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from tests.support import build_settings

if TYPE_CHECKING:
    import pytest


def test_the_values_fill_every_placeholder(tmp_path: Path) -> None:
    settings = build_settings(tmp_path / "web-shop")

    assert settings.values() == {
        "name": "web-shop",
        "app": "web_shop",
        "python": "3.13",
        "minor": "13",
    }


def test_the_command_line_repeats_every_choice_and_asks_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    settings = build_settings(
        tmp_path / "shop", template="webapp", add_ons="orm:sqlite+postgres,lock", name_given=True
    )

    assert settings.command_line() == (
        "uvx xtr-cli new shop --template=webapp --name=shop "
        "--with=orm:sqlite+postgres,lock --python=3.13 -n"
    )


def test_a_directory_outside_the_working_one_is_given_whole(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    elsewhere = Path("/somewhere/shop")

    assert "new /somewhere/shop " in build_settings(elsewhere).command_line()


def test_init_names_no_directory_and_keeps_the_switches(tmp_path: Path) -> None:
    settings = build_settings(
        tmp_path / "shop", command="init", git=False, local_packages=tmp_path / "packages"
    )

    assert settings.command_line() == (
        "uvx xtr-cli init --template=cli --python=3.13 --no-git "
        f"--local-packages={tmp_path / 'packages'} -n"
    )
