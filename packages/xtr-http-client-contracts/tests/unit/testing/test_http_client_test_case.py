"""The conformance suite's shape, which is all this package can check of it.

Its bodies need a client to run against, and a contracts package ships none; what is checkable
here is that the suite offers exactly the tests it says it does, that a subclass inherits every
one of them, and that `skipped_tests` takes them all out of the way.
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, ClassVar

import pytest
from typing_extensions import override

from xtr_http_client_contracts.testing import HttpClientTestCase

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_client_contracts.http_client_interface import HttpClientInterface

PORTED_FROM_THE_REFERENCE_SUITE = 43
ADDED_BY_THIS_CONTRACT = frozenset(
    {
        "test_body_stream",
        "test_send_request_prefers_the_request_headers",
        "test_send_request_resolves_a_relative_request_uri",
        "test_send_request_merges_the_query_option",
        "test_send_request_applies_auth_bearer_only_without_one",
        "test_send_request_refuses_a_body_on_both",
        "test_request_is_send_request_of_the_same_request",
    }
)

EXPECTED_TESTS = frozenset(
    {
        "test_get_request",
        "test_body_stream",
        "test_head_request",
        "test_unsupported_option",
        "test_http_version",
        "test_chunked_encoding",
        "test_client_error",
        "test_ignore_errors",
        "test_dns_error",
        "test_inline_auth",
        "test_bad_request_body",
        "test_304",
        "test_redirects",
        "test_invalid_redirect",
        "test_relative_redirects",
        "test_redirect_307",
        "test_max_redirects",
        "test_post_json",
        "test_post_array",
        "test_post_resource",
        "test_post_callback",
        "test_cancel",
        "test_info_on_canceled_response",
        "test_resolve",
        "test_idn_resolve",
        "test_ipv6_resolve",
        "test_not_a_timeout",
        "test_timeout_on_access",
        "test_timeout_is_not_a_fatal_error",
        "test_timeout_with_active_concurrent_stream",
        "test_timeout_on_initialize",
        "test_timeout_on_destruct",
        "test_destruct",
        "test_proxy",
        "test_no_proxy",
        "test_auto_encoding_request",
        "test_base_uri",
        "test_query",
        "test_informational_response",
        "test_userland_encoding_request",
        "test_gzip_broken",
        "test_max_duration",
        "test_max_connect_duration",
        "test_with_options",
        "test_send_request_prefers_the_request_headers",
        "test_send_request_resolves_a_relative_request_uri",
        "test_send_request_merges_the_query_option",
        "test_send_request_applies_auth_bearer_only_without_one",
        "test_send_request_refuses_a_body_on_both",
        "test_request_is_send_request_of_the_same_request",
    }
)


def declared_tests() -> frozenset[str]:
    return frozenset(name for name in vars(HttpClientTestCase) if name.startswith("test_"))


def test_it_declares_exactly_the_expected_tests() -> None:
    assert declared_tests() == EXPECTED_TESTS


def test_it_declares_one_test_per_ported_reference_method() -> None:
    ported = EXPECTED_TESTS - ADDED_BY_THIS_CONTRACT
    assert len(ported) == PORTED_FROM_THE_REFERENCE_SUITE


def test_every_test_is_a_coroutine_function() -> None:
    for name in declared_tests():
        assert inspect.iscoroutinefunction(getattr(HttpClientTestCase, name)), name


def test_every_test_is_documented() -> None:
    for name in declared_tests():
        assert getattr(HttpClientTestCase, name).__doc__, name


def test_it_is_not_collected_as_a_test_case_itself() -> None:
    assert HttpClientTestCase.__test__ is False


def test_it_skips_nothing_by_default() -> None:
    assert HttpClientTestCase.skipped_tests == {}


def test_it_names_the_reference_method_behind_every_test() -> None:
    documentation = HttpClientTestCase.__doc__ or ""
    assert "create_client" in documentation
    assert "skipped_tests" in documentation


def test_create_client_asks_the_subclass_for_one() -> None:
    with pytest.raises(NotImplementedError):
        _ = HttpClientTestCase().create_client()


class TestEverythingSkipped(HttpClientTestCase):
    """Every inherited test, skipped: the collection itself is what is under test.

    What this proves is that the suite is usable as a base class — every test is collected,
    every one of them resolves its fixtures, and `skipped_tests` is honoured by name. A test
    erroring here would be a mistake in the suite, not in a client.
    """

    __test__: ClassVar[bool] = True

    skipped_tests: ClassVar[Mapping[str, str]] = dict.fromkeys(EXPECTED_TESTS, "structure check")

    @override
    def create_client(self) -> HttpClientInterface:
        pytest.fail("no test should reach the client: every one of them is skipped")
