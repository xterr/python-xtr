"""The receiving side: what an incoming webhook is checked against and read into.

One parser speaks for one sender. It states which requests are that sender's with a
matcher, checks that one is genuine, and gives back the events it carried — or refuses
it, with the answer its sender is to be given.
"""

from __future__ import annotations

from .abstract_request_parser import AbstractRequestParser
from .chain_request_matcher import ChainRequestMatcher
from .is_json_request_matcher import IsJsonRequestMatcher
from .method_request_matcher import MethodRequestMatcher
from .request_matcher_interface import RequestMatcherInterface
from .request_parser import RequestParser
from .request_parser_interface import RequestParserInterface

__all__ = [
    "AbstractRequestParser",
    "ChainRequestMatcher",
    "IsJsonRequestMatcher",
    "MethodRequestMatcher",
    "RequestMatcherInterface",
    "RequestParser",
    "RequestParserInterface",
]
