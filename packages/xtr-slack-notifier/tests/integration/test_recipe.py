"""The shipped recipe reads as recipes:sync reads it, and asks for what the README says."""

from __future__ import annotations

import tomllib
from pathlib import Path

from xtr_notifier.transport import Dsn
from xtr_recipes.recipe_config import RecipeConfig

import xtr_slack_notifier.recipe

_RECIPE = Path(xtr_slack_notifier.recipe.__file__).parent
_README = Path(__file__).parents[2] / "README.md"


def _manifest() -> RecipeConfig:
    with (_RECIPE / "manifest.toml").open("rb") as handle:
        return RecipeConfig.from_toml("xtr-slack-notifier", tomllib.load(handle))


def test_it_lists_no_bundle_and_writes_no_file() -> None:
    manifest = _manifest()

    assert manifest.bundles == {}
    assert manifest.files == {}


def test_it_sets_a_slack_dsn_a_factory_reads() -> None:
    dsn = Dsn(_manifest().env["SLACK_DSN"])

    assert dsn.scheme == "slack"
    assert dsn.get_option("channel") == "CHANNEL"


def test_it_tells_the_application_to_add_the_transport() -> None:
    steps = _manifest().notes.steps

    assert any('slack=env("SLACK_DSN")' in step for step in steps)
    assert any("config/packages/notifier.py" in step for step in steps)


def test_the_readme_names_what_the_recipe_writes() -> None:
    readme = _README.read_text(encoding="utf-8")

    assert all(key in readme for key in _manifest().env)
