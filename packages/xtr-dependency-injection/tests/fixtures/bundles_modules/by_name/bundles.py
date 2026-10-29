"""A bundles module listing one bundle by class and one, from no installed package, by name."""

from __future__ import annotations

from tests.support.bundles import EchoBundle

BUNDLES = {
    EchoBundle: {"all": True},
    "xtr_not_installed_anywhere.bundle:DevToolsBundle": {"dev": True},
}
