from __future__ import annotations

import pytest

from xtr_recipes.exception import InvalidManifestError
from xtr_recipes.key_pair_config import KeyPairConfig
from xtr_recipes.notes_config import NotesConfig
from xtr_recipes.recipe_config import RecipeConfig
from xtr_recipes.secret_config import SecretConfig

GENERATED_SECRET = "%generate(secret)%"


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


def test_it_rejects_a_files_destination_that_climbs_out_of_the_package() -> None:
    with pytest.raises(InvalidManifestError) as exc:
        _ = RecipeConfig.from_toml("xtr-x", {"files": {"../../outside.txt": "files/x.tmpl"}})

    assert exc.value.key == "../../outside.txt"


def test_it_rejects_an_absolute_files_destination() -> None:
    with pytest.raises(InvalidManifestError) as exc:
        _ = RecipeConfig.from_toml("xtr-x", {"files": {"/etc/passwd": "files/x.tmpl"}})

    assert exc.value.key == "/etc/passwd"


def test_it_rejects_a_files_destination_climbing_out_with_backslashes() -> None:
    with pytest.raises(InvalidManifestError) as exc:
        _ = RecipeConfig.from_toml("xtr-x", {"files": {"..\\..\\outside.txt": "files/x.tmpl"}})

    assert exc.value.key == "..\\..\\outside.txt"


def _keyed(key: dict[str, object], env: dict[str, str] | None = None) -> dict[str, object]:
    return {
        "env": {"PASSPHRASE": GENERATED_SECRET} if env is None else env,
        "keys": {"secrets/server.pem": key},
    }


def test_it_parses_a_generated_secret() -> None:
    config = RecipeConfig.from_toml("xtr-x", {"env": {"SECRET": GENERATED_SECRET}})

    assert config.env == {"SECRET": GENERATED_SECRET}
    assert config.secrets == {"SECRET": SecretConfig()}


def test_it_parses_a_configured_generator() -> None:
    spelled = "%generate(secret, bytes=64, encoding=base64, prefix=whsec_)%"

    config = RecipeConfig.from_toml("xtr-x", {"env": {"SECRET": spelled}})

    assert config.secrets == {"SECRET": SecretConfig(64, "base64", "whsec_")}


def test_a_plain_default_is_no_secret() -> None:
    config = RecipeConfig.from_toml("xtr-x", {"env": {"DSN": "amqp://localhost"}})

    assert config.secrets == {}


def test_a_passphrase_may_name_a_configured_generator() -> None:
    data = _keyed(
        {"algorithm": "RS256", "passphrase": "PASSPHRASE"},
        {"PASSPHRASE": "%generate(secret, bytes=48, encoding=hex)%"},
    )

    config = RecipeConfig.from_toml("xtr-x", data)

    assert config.keys["secrets/server.pem"] == KeyPairConfig("RS256", "PASSPHRASE")


def test_it_rejects_an_unknown_generator() -> None:
    with pytest.raises(InvalidManifestError) as exc:
        _ = RecipeConfig.from_toml("xtr-x", {"env": {"SECRET": "%generate(password)%"}})

    assert exc.value.key == "env.SECRET"


def test_it_parses_a_key_with_its_passphrase() -> None:
    config = RecipeConfig.from_toml(
        "xtr-x", _keyed({"algorithm": "RS256", "passphrase": "PASSPHRASE"})
    )

    assert config.keys == {"secrets/server.pem": KeyPairConfig("RS256", "PASSPHRASE")}


def test_it_parses_a_key_with_no_passphrase() -> None:
    config = RecipeConfig.from_toml("xtr-x", _keyed({"algorithm": "ES256"}))

    assert config.keys == {"secrets/server.pem": KeyPairConfig("ES256")}


def test_it_rejects_a_key_algorithm_it_cannot_mint() -> None:
    with pytest.raises(InvalidManifestError) as exc:
        _ = RecipeConfig.from_toml("xtr-x", _keyed({"algorithm": "HS256"}))

    assert exc.value.key == "keys.secrets/server.pem.algorithm"


def test_it_rejects_an_unknown_key_setting() -> None:
    with pytest.raises(InvalidManifestError) as exc:
        _ = RecipeConfig.from_toml("xtr-x", _keyed({"algorithm": "RS256", "size": 4096}))

    assert exc.value.key == "keys.secrets/server.pem.size"


def test_it_rejects_a_passphrase_that_is_not_a_generated_secret() -> None:
    with pytest.raises(InvalidManifestError) as exc:
        _ = RecipeConfig.from_toml(
            "xtr-x",
            _keyed({"algorithm": "RS256", "passphrase": "PASSPHRASE"}, {"PASSPHRASE": "fixed"}),
        )

    assert exc.value.key == "keys.secrets/server.pem.passphrase"


def test_it_rejects_a_key_path_that_climbs_out_of_the_project() -> None:
    with pytest.raises(InvalidManifestError) as exc:
        _ = RecipeConfig.from_toml("xtr-x", {"keys": {"../server.pem": {"algorithm": "RS256"}}})

    assert exc.value.key == "../server.pem"


def test_it_parses_a_key_with_its_path_variable() -> None:
    data = _keyed(
        {"algorithm": "RS256", "path_env": "KEY_PATH"},
        {"KEY_PATH": "%kernel.project_dir%/secrets/server.pem"},
    )

    config = RecipeConfig.from_toml("xtr-x", data)

    assert config.keys["secrets/server.pem"].path_env == "KEY_PATH"


def test_it_rejects_a_path_variable_naming_another_file() -> None:
    data = _keyed(
        {"algorithm": "RS256", "path_env": "KEY_PATH"},
        {"KEY_PATH": "%kernel.project_dir%/secrets/other.pem"},
    )

    with pytest.raises(InvalidManifestError) as exc:
        _ = RecipeConfig.from_toml("xtr-x", data)

    assert exc.value.key == "keys.secrets/server.pem.path_env"
