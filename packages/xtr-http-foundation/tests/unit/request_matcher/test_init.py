"""The matchers are reachable from the folder that groups them and from the package."""

from __future__ import annotations

import xtr_http_foundation
from xtr_http_foundation import request_matcher

_MATCHERS = (
    "AttributesRequestMatcher",
    "CallableRequestMatcher",
    "HeaderRequestMatcher",
    "HostRequestMatcher",
    "IpsRequestMatcher",
    "IsJsonRequestMatcher",
    "MethodRequestMatcher",
    "PathRequestMatcher",
    "PortRequestMatcher",
    "QueryParameterRequestMatcher",
    "SchemeRequestMatcher",
)


def test_the_folder_exports_every_matcher() -> None:
    assert sorted(request_matcher.__all__) == sorted(_MATCHERS)


def test_the_package_exports_the_same_matchers() -> None:
    for name in _MATCHERS:
        assert getattr(xtr_http_foundation, name) is getattr(request_matcher, name)
