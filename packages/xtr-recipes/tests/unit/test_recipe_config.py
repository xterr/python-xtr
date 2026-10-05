from __future__ import annotations

import pytest

from xtr_recipes.exception import InvalidManifestError
from xtr_recipes.notes_config import NotesConfig
from xtr_recipes.recipe_config import RecipeConfig


def test_it_parses_a_full_manifest() -> None:
    data: dict[str, object] = {
        "bundles": {"xtr_messenger.bundle:MessengerBundle": {"all": True}},
        "files": {"config/messenger.py": "files/config/messenger.py.tmpl"},
        "env": {"MESSENGER_DSN": ""},
        "gitignore": {"lines": ["/var/messages"]},
        "notes": {
            "steps": ["edit the kernel"],
            "check": ["debug:bundles"],
            "run": ["messenger:consume"],
        },
    }

    config = RecipeConfig.from_toml("xtr-messenger", data)

    assert config.bundles == {"xtr_messenger.bundle:MessengerBundle": {"all": True}}
    assert config.files == {"config/messenger.py": "files/config/messenger.py.tmpl"}
    assert config.env == {"MESSENGER_DSN": ""}
    assert config.gitignore == ("/var/messages",)
    assert config.notes == NotesConfig(
        steps=("edit the kernel",),
        check=("debug:bundles",),
        run=("messenger:consume",),
    )


def test_an_empty_manifest_is_an_empty_recipe() -> None:
    config = RecipeConfig.from_toml("xtr-x", {})

    assert config.bundles == {}
    assert config.files == {}
    assert config.env == {}
    assert config.gitignore == ()
    assert config.notes == NotesConfig()


def test_it_rejects_an_unknown_table() -> None:
    with pytest.raises(InvalidManifestError) as exc:
        _ = RecipeConfig.from_toml("xtr-x", {"scripts": {}})

    assert exc.value.package == "xtr-x"
    assert exc.value.key == "scripts"


def test_it_rejects_an_unknown_notes_key() -> None:
    with pytest.raises(InvalidManifestError) as exc:
        _ = RecipeConfig.from_toml("xtr-x", {"notes": {"wat": []}})

    assert exc.value.key == "notes.wat"


def test_it_rejects_an_unknown_gitignore_key() -> None:
    with pytest.raises(InvalidManifestError) as exc:
        _ = RecipeConfig.from_toml("xtr-x", {"gitignore": {"wat": []}})

    assert exc.value.key == "gitignore.wat"


def test_it_rejects_a_malformed_bundle_target() -> None:
    with pytest.raises(InvalidManifestError) as exc:
        _ = RecipeConfig.from_toml("xtr-x", {"bundles": {"not-a-target": {"all": True}}})

    assert exc.value.key == "not-a-target"


def test_it_rejects_a_non_boolean_flag() -> None:
    with pytest.raises(InvalidManifestError) as exc:
        _ = RecipeConfig.from_toml("xtr-x", {"bundles": {"m.b:B": {"all": 1}}})

    assert exc.value.key == "m.b:B.all"


def test_it_rejects_flags_that_are_not_a_table() -> None:
    with pytest.raises(InvalidManifestError) as exc:
        _ = RecipeConfig.from_toml("xtr-x", {"bundles": {"m.b:B": "nope"}})

    assert exc.value.key == "m.b:B"


def test_it_rejects_a_non_string_file_template() -> None:
    with pytest.raises(InvalidManifestError) as exc:
        _ = RecipeConfig.from_toml("xtr-x", {"files": {"config/x.py": 3}})

    assert exc.value.key == "files.config/x.py"


def test_it_rejects_a_non_string_env_default() -> None:
    with pytest.raises(InvalidManifestError) as exc:
        _ = RecipeConfig.from_toml("xtr-x", {"env": {"KEY": 3}})

    assert exc.value.key == "env.KEY"


def test_it_rejects_a_table_where_a_list_is_expected() -> None:
    with pytest.raises(InvalidManifestError) as exc:
        _ = RecipeConfig.from_toml("xtr-x", {"gitignore": {"lines": "nope"}})

    assert exc.value.key == "gitignore.lines"


def test_it_rejects_a_non_string_in_a_list() -> None:
    with pytest.raises(InvalidManifestError) as exc:
        _ = RecipeConfig.from_toml("xtr-x", {"notes": {"run": [1]}})

    assert exc.value.key == "notes.run"


def test_it_rejects_a_table_that_is_not_a_table() -> None:
    with pytest.raises(InvalidManifestError) as exc:
        _ = RecipeConfig.from_toml("xtr-x", {"bundles": "nope"})

    assert exc.value.key == "bundles"


def test_it_rejects_a_non_string_table_key() -> None:
    with pytest.raises(InvalidManifestError) as exc:
        _ = RecipeConfig.from_toml("xtr-x", {"files": {123: "y"}})

    assert exc.value.key == "files"
