from __future__ import annotations

from xtr_http_message_contracts import ResponseInterface

from tests.support.fake_response import FakeResponse
from xtr_http_client_contracts import HttpResponseInterface


def test_a_response_answering_every_question_satisfies_it() -> None:
    response: HttpResponseInterface = FakeResponse()

    assert isinstance(response, HttpResponseInterface)


def test_an_unrelated_object_does_not() -> None:
    assert not isinstance(object(), HttpResponseInterface)


def test_it_is_an_http_response_before_it_is_anything_else() -> None:
    assert issubclass(HttpResponseInterface, ResponseInterface)


def test_a_client_response_is_therefore_also_a_message_response() -> None:
    response: ResponseInterface = FakeResponse()

    assert isinstance(response, ResponseInterface)
