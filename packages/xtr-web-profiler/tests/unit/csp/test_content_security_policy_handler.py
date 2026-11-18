from __future__ import annotations

import re

import pytest
from starlette.datastructures import MutableHeaders

from xtr_web_profiler.csp import ContentSecurityPolicyHandler, NonceGenerator


def _handler() -> ContentSecurityPolicyHandler:
    return ContentSecurityPolicyHandler(NonceGenerator())


_NONCES = {"csp_script_nonce": "s1", "csp_style_nonce": "t1"}


def test_the_requests_own_nonces_are_reused() -> None:
    nonces = _handler().get_nonces(
        {"x-profiler-script-nonce": "abc", "x-profiler-style-nonce": "def"}
    )

    assert nonces == {"csp_script_nonce": "abc", "csp_style_nonce": "def"}


def test_fresh_nonces_are_made_when_the_request_has_none() -> None:
    nonces = _handler().get_nonces({})

    assert set(nonces) == {"csp_script_nonce", "csp_style_nonce"}
    assert all(re.fullmatch(r"[0-9a-f]{32}", nonce) for nonce in nonces.values())
    assert nonces["csp_script_nonce"] != nonces["csp_style_nonce"]


@pytest.mark.parametrize(
    ("policy", "expected"),
    [
        (
            "script-src 'self'; style-src 'self'",
            (
                "script-src 'self' 'unsafe-inline' 'nonce-s1'; "
                "style-src 'self' 'unsafe-inline' 'nonce-t1'"
            ),
        ),
        (
            "default-src 'self'",
            (
                "default-src 'self'; script-src 'self' 'unsafe-inline' 'nonce-s1'; "
                "style-src 'self' 'unsafe-inline' 'nonce-t1'"
            ),
        ),
        (
            "script-src 'unsafe-inline'; style-src 'none'",
            "script-src 'unsafe-inline'; style-src 'unsafe-inline' 'nonce-t1'",
        ),
        (
            "script-src 'unsafe-inline' 'nonce-x'; script-src-elem 'self'",
            (
                "script-src 'unsafe-inline' 'nonce-x' 'unsafe-inline' 'nonce-s1'; "
                "script-src-elem 'self' 'unsafe-inline' 'nonce-s1'"
            ),
        ),
        ("img-src *", "img-src *"),
    ],
    ids=["own-directives", "default-src", "already-inline", "elem-and-nonce", "unrelated"],
)
def test_the_nonces_join_every_script_and_style_directive(policy: str, expected: str) -> None:
    headers = MutableHeaders({"content-security-policy": policy})

    _handler().update_response_headers(_NONCES, headers)

    assert headers["content-security-policy"] == expected


def test_a_response_without_a_policy_is_left_alone() -> None:
    headers = MutableHeaders({"content-type": "text/html"})

    _handler().update_response_headers(_NONCES, headers)

    assert dict(headers) == {"content-type": "text/html"}


def test_disabling_removes_every_policy_header() -> None:
    headers = MutableHeaders(
        {
            "content-security-policy": "default-src 'self'",
            "content-security-policy-report-only": "default-src 'self'",
            "content-type": "text/html",
        }
    )

    _handler().disable_csp(headers)

    assert dict(headers) == {"content-type": "text/html"}
