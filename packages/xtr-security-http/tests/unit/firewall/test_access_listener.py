"""The access listener decides a request against its firewall's rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_security_core.authentication.token.null_token import NullToken
from xtr_security_core.authorization import AccessDecisionManager, RoleVoter
from xtr_security_core.authorization.voter.authenticated_voter import AuthenticatedVoter
from xtr_security_core.exception import AccessDeniedError
from xtr_security_core.user.in_memory_user import InMemoryUser

from tests.support.requests import make_request
from xtr_security_http.access_map import AccessMap
from xtr_security_http.authenticator.token.post_authentication_token import PostAuthenticationToken
from xtr_security_http.firewall.access_listener import AccessListener
from xtr_security_http.request_matcher.path_request_matcher import PathRequestMatcher

if TYPE_CHECKING:
    from starlette.requests import Request

pytestmark = pytest.mark.anyio


def _listener(*rules: tuple[str, str]) -> AccessListener:
    access_map = AccessMap()
    for path, attribute in rules:
        access_map.add(PathRequestMatcher(path), attribute)
    return AccessListener(access_map, AccessDecisionManager([RoleVoter()]))


def _request(path: str) -> Request:
    request = make_request()
    request.scope["path"] = path
    return request


async def test_a_matching_granted_rule_passes() -> None:
    listener = _listener((r"^/api", "ROLE_USER"))
    token = PostAuthenticationToken(InMemoryUser("alice"), "api", ["ROLE_USER"])

    await listener.check_access(_request("/api/books"), token)


async def test_a_matching_denied_rule_is_refused() -> None:
    listener = _listener((r"^/api", "ROLE_ADMIN"))
    token = PostAuthenticationToken(InMemoryUser("alice"), "api", ["ROLE_USER"])

    with pytest.raises(AccessDeniedError):
        await listener.check_access(_request("/api/books"), token)


async def test_a_public_access_rule_short_circuits() -> None:
    listener = _listener((r"^/api", AuthenticatedVoter.PUBLIC_ACCESS))

    await listener.check_access(_request("/api/books"), NullToken())


async def test_a_request_matching_no_rule_is_left_alone() -> None:
    listener = _listener((r"^/admin", "ROLE_ADMIN"))

    await listener.check_access(_request("/public"), NullToken())
