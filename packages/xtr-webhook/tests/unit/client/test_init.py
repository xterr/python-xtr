from __future__ import annotations

from xtr_webhook import client


def test_it_publishes_the_receiving_side() -> None:
    assert sorted(client.__all__) == [
        "AbstractRequestParser",
        "ChainRequestMatcher",
        "IsJsonRequestMatcher",
        "MethodRequestMatcher",
        "RequestMatcherInterface",
        "RequestParser",
        "RequestParserInterface",
    ]


def test_everything_it_publishes_is_there() -> None:
    assert all(hasattr(client, name) for name in client.__all__)
