"""The receiving side: what an incoming webhook is checked against and read into.

One parser speaks for one sender. It states which requests are that sender's with a
matcher, checks that one is genuine, and gives back the events it carried — or refuses
it, with the answer its sender is to be given.

The matchers themselves come from
[xtr-http-foundation](https://pypi.org/project/xtr-http-foundation/), so a webhook
endpoint says which requests are its sender's the same way a firewall or a rate limiter
does.
"""

from __future__ import annotations

from .abstract_request_parser import AbstractRequestParser
from .request_parser import RequestParser
from .request_parser_interface import RequestParserInterface

__all__ = [
    "AbstractRequestParser",
    "RequestParser",
    "RequestParserInterface",
]
