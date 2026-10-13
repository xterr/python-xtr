"""The import package is importable and ships the marker that publishes its types."""

from __future__ import annotations

from importlib.resources import files

import xtr_http_foundation


def test_the_package_ships_its_typing_marker() -> None:
    assert files("xtr_http_foundation").joinpath("py.typed").is_file()


def test_everything_it_exports_is_reachable() -> None:
    for name in xtr_http_foundation.__all__:
        assert getattr(xtr_http_foundation, name, None) is not None


def test_it_exports_the_matcher_contract_and_the_chain() -> None:
    assert {"RequestMatcherInterface", "ChainRequestMatcher", "IpUtils"} <= set(
        xtr_http_foundation.__all__
    )
