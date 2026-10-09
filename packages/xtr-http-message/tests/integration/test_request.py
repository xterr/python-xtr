from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_http_message_contracts import UriInterface

from xtr_http_message.uri import Uri

if TYPE_CHECKING:
    from xtr_http_message_contracts import RequestInterface

# The harness checks that a method of the wrong type is refused. Here the type
# is in the signature, so the call cannot be made at all.
_WRONG_TYPE = (
    "Adaptation (plan H2): a method is typed `str`, so the four rows of the harness's provider "
    "— nothing, a boolean, a list and a bare object — are refused before the call; no run-time "
    "type check was ported, and the implementation this package ports has none either."
)


def test_the_request_target_is_the_path_of_the_uri(request_subject: RequestInterface) -> None:
    assert request_subject.get_request_target() == "/"


def test_the_request_target_can_be_set_by_hand(request_subject: RequestInterface) -> None:
    by_hand = request_subject.with_request_target("*")

    assert by_hand is not request_subject
    assert request_subject.get_request_target() == "/"
    assert by_hand.get_request_target() == "*"


def test_the_method_can_be_replaced(request_subject: RequestInterface) -> None:
    replaced = request_subject.with_method("POST")

    assert replaced is not request_subject
    assert request_subject.get_method() == "GET"
    assert replaced.get_method() == "POST"


def test_a_method_keeps_the_case_it_was_given_in(request_subject: RequestInterface) -> None:
    assert request_subject.with_method("head").get_method() == "head"


def test_a_method_outside_the_standard_ones_is_accepted(
    request_subject: RequestInterface,
) -> None:
    assert request_subject.with_method("CUSTOM").get_method() == "CUSTOM"


@pytest.mark.skip(reason=_WRONG_TYPE)
def test_a_method_of_the_wrong_type_is_refused() -> None:
    """The rows of the harness that pass something which is not a method."""


def test_the_uri_of_a_request_is_a_uri(request_subject: RequestInterface) -> None:
    assert isinstance(request_subject.get_uri(), UriInterface)


def test_setting_the_uri_sets_the_host_header(request_subject: RequestInterface) -> None:
    uri = Uri("http://www.foo.com/bar")

    carrying = request_subject.with_uri(uri)

    assert carrying is not request_subject
    assert request_subject.get_header_line("host") == ""
    assert carrying.get_header_line("host") == "www.foo.com"
    assert str(carrying.get_uri()) == "http://www.foo.com/bar"


def test_a_uri_with_no_host_carries_the_host_header_over(
    request_subject: RequestInterface,
) -> None:
    carrying = request_subject.with_uri(Uri("http://www.foo.com/bar"))

    relative = carrying.with_uri(Uri("/foobar"))

    assert relative.get_header_line("host") == "www.foo.com"
    assert str(relative.get_uri()) == "/foobar"


def test_a_host_asked_to_be_preserved_is_taken_from_the_uri_when_there_is_none(
    request_subject: RequestInterface,
) -> None:
    preserved = request_subject.with_uri(Uri("http://www.foo.com/bar"), preserve_host=True)

    assert preserved.get_header_line("host") == "www.foo.com"


def test_a_host_asked_to_be_preserved_stays_absent_when_the_uri_has_none(
    request_subject: RequestInterface,
) -> None:
    before = request_subject.get_header_line("host")

    preserved = request_subject.with_uri(Uri("/bar"), preserve_host=True)

    assert preserved.get_header_line("host") == before


def test_a_host_asked_to_be_preserved_survives_a_uri_naming_another(
    request_subject: RequestInterface,
) -> None:
    carrying = request_subject.with_uri(Uri("http://www.foo.com/bar"))

    preserved = carrying.with_uri(Uri("http://www.bar.com/foo"), preserve_host=True)

    assert preserved.get_header_line("host") == carrying.get_header_line("host")


def test_the_request_target_reduces_the_leading_slashes_of_the_path(
    request_subject: RequestInterface,
) -> None:
    """A path read in isolation must not read as an authority, which would poison the URL.

    See https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2015-3257.
    """
    carrying = request_subject.with_uri(Uri("http://example.org//valid///path"))

    assert carrying.get_request_target() == "/valid///path"
