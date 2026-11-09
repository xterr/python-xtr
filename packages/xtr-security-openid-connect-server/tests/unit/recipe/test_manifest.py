"""The recipe shipped in the package lists the package's own bundle."""

from __future__ import annotations

import importlib
import tomllib
from importlib.resources import files
from typing import cast

from xtr_security_openid_connect_server.bundle import OpenIdConnectServerBundle

_RECIPE = "xtr_security_openid_connect_server.recipe"


def _listed() -> dict[str, dict[str, bool]]:
    """Return the manifest's bundle targets, each mapped to its environment flags."""
    manifest: dict[str, object] = tomllib.loads(
        files(_RECIPE).joinpath("manifest.toml").read_text(encoding="utf-8")
    )
    return cast("dict[str, dict[str, bool]]", manifest["bundles"])


def _named_by(target: str) -> object:
    """Return what a ``"module:Class"`` target names, imported as the kernel imports it."""
    module, _, name = target.partition(":")
    return cast("object", getattr(importlib.import_module(module), name))


def test_the_recipe_lists_this_packages_bundle_in_every_environment() -> None:
    listed = {_named_by(target): flags for target, flags in _listed().items()}

    assert listed == {OpenIdConnectServerBundle: {"all": True}}
