"""The package every other contract package may depend on stays a leaf."""

from __future__ import annotations

from importlib.metadata import requires


def test_it_requires_nothing_at_runtime() -> None:
    runtime = [
        requirement
        for requirement in requires("xtr-service-contracts") or []
        if "extra ==" not in requirement
    ]

    assert runtime == []
