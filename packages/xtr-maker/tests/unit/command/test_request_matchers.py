"""Unit tests for :mod:`xtr_maker.command._request_matchers`."""

from __future__ import annotations

import xtr_http_foundation
from xtr_http_foundation import RequestMatcherInterface

from xtr_maker import ImportCollector
from xtr_maker.command._request_matchers import REQUEST_MATCHERS, request_matcher_body


def test_every_matcher_offered_is_one_the_library_exports() -> None:
    exported = set(xtr_http_foundation.__all__)

    assert {choice.class_name for choice in REQUEST_MATCHERS} <= exported


def test_every_placeholder_builds_its_matcher() -> None:
    namespace = {**vars(xtr_http_foundation), "_SIGNATURE_HEADER": "Acme-Signature"}

    for choice in REQUEST_MATCHERS:
        source = f"{choice.class_name}({choice.arguments})"

        assert isinstance(
            eval(source, namespace),  # noqa: S307 — the maker's own constants, no input.
            RequestMatcherInterface,
        ), choice.name


def test_one_matcher_is_imported_without_the_chain() -> None:
    imports = ImportCollector("app")

    body = request_matcher_body(REQUEST_MATCHERS[-1:], imports)

    assert body == '        return SchemeRequestMatcher("https")'
    assert imports.render() == "from xtr_http_foundation import SchemeRequestMatcher"
