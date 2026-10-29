"""RecipeConfig: the declarative content a recipe applies to an application."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, final

from .exception import InvalidManifestError
from .key_pair_config import KEY_ALGORITHMS, PROJECT_DIR, KeyPairConfig
from .notes_config import NotesConfig
from .safe_path import has_traversal
from .secret_config import SecretConfig

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["BUNDLE_TARGET", "COMPOSE_FILES", "RecipeConfig"]

COMPOSE_FILES = ("compose.yaml", "compose.override.yaml")
"""The Compose files a recipe may write into: the services, and their local-only overrides."""

BUNDLE_TARGET = re.compile(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*:[A-Za-z_]\w*")
"""A bundle target, ``"<dotted module>:<ClassName>"``, exactly as it reads in ``BUNDLES``.

The manifest names a bundle this way, and so does a ``BUNDLES`` key listing one by name.
"""

_TABLES = frozenset({"bundles", "files", "env", "keys", "gitignore", "compose", "notes"})
_NOTES_KEYS = ("steps", "check", "run")
_GITIGNORE_KEYS = frozenset({"lines"})
_KEY_PAIR_KEYS = frozenset({"algorithm", "passphrase", "path_env"})
# A Compose top-level key: services, volumes, networks, configs, secrets.
_COMPOSE_KEY = re.compile(r"[A-Za-z0-9_-]+")


@final
@dataclass(frozen=True, slots=True)
class RecipeConfig:
    """Everything a recipe declares, parsed from its ``manifest.toml``.

    Built by :meth:`from_toml`, which is the trust boundary: it is the only
    place untrusted manifest data is turned into these typed fields, so the
    rest of the library receives a value it never has to re-check. A hand-built
    instance is trusted as given.

    Attributes:
        bundles: Each bundle target (``"module:Class"``) mapped to the
            environment flags it is listed with, as they appear in ``BUNDLES``.
        files: Each destination, relative to the application package, mapped to
            its template path relative to the recipe.
        env: Each environment variable mapped to its default, ``""`` meaning no
            default (written commented out so the variable stays unset) and a
            ``%generate(secret, …)%`` placeholder a fresh secret made when the
            line is written.
        secrets: Each environment variable whose default is a generator, mapped
            to how its secret is made.
        keys: Each private key to mint, relative to the project directory,
            mapped to its algorithm and the env key encrypting it.
        gitignore: The ``.gitignore`` lines the recipe contributes.
        compose: Each Compose file, one of :data:`COMPOSE_FILES`, mapped to its
            top-level keys, each mapped to the YAML lines the recipe puts under it.
        notes: What the recipe prints rather than does.
    """

    bundles: Mapping[str, Mapping[str, bool]] = field(default_factory=dict)
    files: Mapping[str, str] = field(default_factory=dict)
    env: Mapping[str, str] = field(default_factory=dict)
    secrets: Mapping[str, SecretConfig] = field(default_factory=dict[str, SecretConfig])
    keys: Mapping[str, KeyPairConfig] = field(default_factory=dict[str, KeyPairConfig])
    gitignore: tuple[str, ...] = ()
    compose: Mapping[str, Mapping[str, tuple[str, ...]]] = field(default_factory=dict)
    notes: NotesConfig = field(default_factory=NotesConfig)

    @classmethod
    def from_toml(cls, package: str, data: Mapping[str, object]) -> RecipeConfig:
        """Parse one recipe's manifest, validating every table, key and value.

        Args:
            package: The distribution whose manifest this is, named in errors.
            data: The manifest, already read from TOML into a mapping.

        Returns:
            The parsed, validated recipe content.

        Raises:
            InvalidManifestError: On an unknown table, an unknown key, a
                malformed ``"module:Class"`` bundle target, an unknown
                generator or key algorithm, or a value of the wrong type — each
                naming the package and the key at fault.
        """
        unknown = sorted(set(data) - _TABLES)
        if unknown:
            raise InvalidManifestError(package, unknown[0], "unknown table")
        env = _read_env(package, data.get("env"))
        generated = _read_secrets(package, env)
        return cls(
            bundles=_read_bundles(package, data.get("bundles")),
            files=_read_files(package, data.get("files")),
            env=env,
            secrets=generated,
            keys=_read_keys(package, data.get("keys"), env, generated),
            gitignore=_read_gitignore(package, data.get("gitignore")),
            compose=_read_compose(package, data.get("compose")),
            notes=_read_notes(package, data.get("notes")),
        )


def _as_table(package: str, key: str, value: object) -> dict[str, object]:
    """Return ``value`` as a table of string keys, or ``{}`` when absent."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise InvalidManifestError(package, key, "must be a table")
    table: dict[str, object] = {}
    for name, item in value.items():
        if not isinstance(name, str):
            raise InvalidManifestError(package, key, "every key must be a string")
        table[name] = item
    return table


def _read_bundles(package: str, value: object) -> dict[str, dict[str, bool]]:
    """Parse the ``[bundles]`` table: each target mapped to its flags."""
    result: dict[str, dict[str, bool]] = {}
    for target, flags in _as_table(package, "bundles", value).items():
        if BUNDLE_TARGET.fullmatch(target) is None:
            raise InvalidManifestError(package, target, "expected '<module>:<Class>'")
        result[target] = _read_flags(package, target, flags)
    return result


def _read_flags(package: str, target: str, value: object) -> dict[str, bool]:
    """Parse one bundle's environment flags: a table of booleans."""
    result: dict[str, bool] = {}
    for name, flag in _as_table(package, target, value).items():
        if not isinstance(flag, bool):
            raise InvalidManifestError(package, f"{target}.{name}", "flag must be true or false")
        result[name] = flag
    return result


def _read_strings(package: str, key: str, value: object) -> dict[str, str]:
    """Parse a table whose every value must be a string."""
    result: dict[str, str] = {}
    for name, item in _as_table(package, key, value).items():
        if not isinstance(item, str):
            raise InvalidManifestError(package, f"{key}.{name}", "must be a string")
        result[name] = item
    return result


def _read_env(package: str, value: object) -> dict[str, str]:
    """Parse the ``[env]`` table: every key mapped to its default, as written."""
    return _read_strings(package, "env", value)


def _read_secrets(package: str, env: Mapping[str, str]) -> dict[str, SecretConfig]:
    """Return how each generated default is made, refusing a misspelt generator."""
    result: dict[str, SecretConfig] = {}
    for name, default in env.items():
        secret = SecretConfig.parse(package, name, default)
        if secret is not None:
            result[name] = secret
    return result


def _read_keys(
    package: str,
    value: object,
    env: Mapping[str, str],
    generated: Mapping[str, SecretConfig],
) -> dict[str, KeyPairConfig]:
    """Parse the ``[keys]`` table: each private key's path, algorithm and pass phrase.

    A path is relative to the project directory and refused when it would climb
    out of it. A pass phrase names an ``[env]`` key whose default is a
    generated secret: the key is encrypted with that very secret, so the
    application reads back the value it was sealed with.
    """
    result: dict[str, KeyPairConfig] = {}
    for destination, entry in _as_table(package, "keys", value).items():
        if has_traversal(destination):
            raise InvalidManifestError(
                package, destination, "key path must be a relative path inside the project"
            )
        table = _as_table(package, f"keys.{destination}", entry)
        unknown = sorted(set(table) - _KEY_PAIR_KEYS)
        if unknown:
            raise InvalidManifestError(package, f"keys.{destination}.{unknown[0]}", "unknown key")
        algorithm = table.get("algorithm")
        if algorithm not in KEY_ALGORITHMS:
            raise InvalidManifestError(
                package,
                f"keys.{destination}.algorithm",
                f"must be one of {', '.join(KEY_ALGORITHMS)}",
            )
        passphrase = table.get("passphrase")
        if passphrase is not None and (
            not isinstance(passphrase, str) or passphrase not in generated
        ):
            raise InvalidManifestError(
                package,
                f"keys.{destination}.passphrase",
                "must name an [env] key whose default is a %generate(secret, …)% generator",
            )
        path_env = table.get("path_env")
        expected = f"{PROJECT_DIR}/{destination}"
        if path_env is not None and (
            not isinstance(path_env, str) or env.get(path_env) != expected
        ):
            raise InvalidManifestError(
                package,
                f"keys.{destination}.path_env",
                f"must name an [env] key whose default is {expected}",
            )
        result[destination] = KeyPairConfig(str(algorithm), passphrase, path_env)
    return result


def _read_files(package: str, value: object) -> dict[str, str]:
    """Parse the ``[files]`` table: each destination mapped to its template.

    A destination is written relative to the application package, so an
    absolute one or one climbing out with ``..`` would let a recipe write
    anywhere on disk; it is refused here, at the trust boundary, rather than
    caught when the planner joins it to a directory.
    """
    result: dict[str, str] = {}
    for destination, template in _as_table(package, "files", value).items():
        if not isinstance(template, str):
            raise InvalidManifestError(package, f"files.{destination}", "must be a string")
        if has_traversal(destination):
            raise InvalidManifestError(
                package, destination, "destination must be a relative path inside the package"
            )
        result[destination] = template
    return result


def _read_gitignore(package: str, value: object) -> tuple[str, ...]:
    """Parse the ``[gitignore]`` table: only a ``lines`` list of strings."""
    table = _as_table(package, "gitignore", value)
    unknown = sorted(set(table) - _GITIGNORE_KEYS)
    if unknown:
        raise InvalidManifestError(package, f"gitignore.{unknown[0]}", "unknown key")
    return _read_str_list(package, "gitignore.lines", table.get("lines"))


def _read_notes(package: str, value: object) -> NotesConfig:
    """Parse the ``[notes]`` table: only ``steps``, ``check`` and ``run`` lists."""
    table = _as_table(package, "notes", value)
    unknown = sorted(set(table) - set(_NOTES_KEYS))
    if unknown:
        raise InvalidManifestError(package, f"notes.{unknown[0]}", "unknown key")
    return NotesConfig(
        steps=_read_str_list(package, "notes.steps", table.get("steps")),
        check=_read_str_list(package, "notes.check", table.get("check")),
        run=_read_str_list(package, "notes.run", table.get("run")),
    )


def _read_compose(package: str, value: object) -> dict[str, dict[str, tuple[str, ...]]]:
    """Parse the ``[compose]`` table: each file's top-level keys and the YAML under each.

    The YAML is kept line for line, indentation and comments included, and is
    never substituted: ``${POSTGRES_DB:-app}`` is Compose's own interpolation.
    """
    result: dict[str, dict[str, tuple[str, ...]]] = {}
    for name, sections in _as_table(package, "compose", value).items():
        if name not in COMPOSE_FILES:
            raise InvalidManifestError(
                package, f"compose.{name}", f"must be one of {', '.join(COMPOSE_FILES)}"
            )
        parsed: dict[str, tuple[str, ...]] = {}
        for key, text in _as_table(package, f"compose.{name}", sections).items():
            where = f"compose.{name}.{key}"
            if _COMPOSE_KEY.fullmatch(key) is None:
                raise InvalidManifestError(package, where, "must be a Compose top-level key")
            if not isinstance(text, str) or not text.strip():
                raise InvalidManifestError(package, where, "must be a non-empty string of YAML")
            parsed[key] = tuple(text.rstrip().splitlines())
        result[name] = parsed
    return result


def _read_str_list(package: str, key: str, value: object) -> tuple[str, ...]:
    """Return ``value`` as a tuple of strings, or ``()`` when absent."""
    if value is None:
        return ()
    if not isinstance(value, list):
        raise InvalidManifestError(package, key, "must be a list")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise InvalidManifestError(package, key, "every entry must be a string")
        items.append(item)
    return tuple(items)
