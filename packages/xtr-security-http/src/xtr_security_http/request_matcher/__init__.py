"""Request matchers: which requests a firewall's access rule claims.

A rule pairs one of these with an attribute in an
:class:`~xtr_security_http.access_map.AccessMap`; the first matcher that claims
a request decides it. The matchers compose — a
:class:`~xtr_security_http.request_matcher.chain_request_matcher.ChainRequestMatcher`
holds a path, host, method and address matcher when a rule constrains all four.
"""

from __future__ import annotations

from .callable_request_matcher import CallableRequestMatcher
from .chain_request_matcher import ChainRequestMatcher
from .host_request_matcher import HostRequestMatcher
from .ip_request_matcher import IpRequestMatcher
from .method_request_matcher import MethodRequestMatcher
from .path_request_matcher import PathRequestMatcher
from .request_matcher_interface import RequestMatcherInterface

__all__ = [
    "CallableRequestMatcher",
    "ChainRequestMatcher",
    "HostRequestMatcher",
    "IpRequestMatcher",
    "MethodRequestMatcher",
    "PathRequestMatcher",
    "RequestMatcherInterface",
]
