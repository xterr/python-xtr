from __future__ import annotations

from tests.support.fake_http_sender import FakeHttpSender
from xtr_webhook.server import HttpSenderInterface


def test_the_fake_this_suite_posts_through_satisfies_it() -> None:
    assert isinstance(FakeHttpSender(), HttpSenderInterface)


def test_something_that_cannot_post_does_not() -> None:
    assert not isinstance(object(), HttpSenderInterface)


def test_anything_that_posts_satisfies_it() -> None:
    class Elsewhere:
        async def post(self, url: str, headers: object, body: bytes) -> int:
            del url, headers, body
            return 200

    assert isinstance(Elsewhere(), HttpSenderInterface)
