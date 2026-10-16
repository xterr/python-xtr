"""The import package is importable and ships the marker that publishes its types."""

from __future__ import annotations

from importlib.resources import files

import xtr_security_csrf


def test_the_package_ships_its_typing_marker() -> None:
    assert files("xtr_security_csrf").joinpath("py.typed").is_file()


def test_everything_it_exports_is_reachable() -> None:
    for name in xtr_security_csrf.__all__:
        assert getattr(xtr_security_csrf, name, None) is not None


def test_it_exports_the_token_the_manager_and_the_storages() -> None:
    assert {
        "CsrfToken",
        "CsrfTokenManager",
        "CsrfTokenManagerInterface",
        "TokenGeneratorInterface",
        "UriSafeTokenGenerator",
        "TokenStorageInterface",
        "ClearableTokenStorageInterface",
        "SessionTokenStorage",
    } <= set(xtr_security_csrf.__all__)
