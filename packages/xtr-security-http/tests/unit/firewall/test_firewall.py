"""The firewall dependency, decorator and router forms."""

from __future__ import annotations

import inspect
from typing import cast

import pytest
from fastapi import APIRouter
from fastapi.params import Security

from xtr_security_http.firewall import Firewall
from xtr_security_http.firewall_scheme import FirewallScheme


def test_a_firewall_is_a_security_marker_with_its_scheme() -> None:
    firewall = Firewall("api")

    assert isinstance(firewall, Security)
    assert isinstance(firewall.dependency, FirewallScheme)
    assert firewall.firewall_name == "api"


def test_scoped_shares_the_scheme_and_adds_scopes() -> None:
    api = Firewall("api")

    scoped = api.scoped("books:read", "books:write")

    assert scoped.dependency is api.dependency
    assert scoped.scopes == ["books:read", "books:write"]
    assert scoped.firewall_name == "api"


def test_an_unbound_firewall_has_no_name() -> None:
    assert Firewall().firewall_name is None


def test_it_decorates_a_router_before_its_routes() -> None:
    router = APIRouter()
    api = Firewall("api")

    returned = api(router)

    assert returned is router
    assert api in router.dependencies


def test_it_decorates_an_endpoint_with_a_hidden_dependency() -> None:
    api = Firewall("api")

    @api
    async def endpoint(book: str) -> str:
        return book

    parameters = inspect.signature(endpoint).parameters
    hidden = [name for name in parameters if name.startswith("_xtr_firewall_")]
    assert len(hidden) == 1
    default = cast("object", parameters[hidden[0]].default)
    assert default is api


def test_it_decorates_a_sync_endpoint() -> None:
    api = Firewall("api")

    @api
    def endpoint() -> str:
        return "ok"

    assert endpoint() == "ok"


@pytest.mark.anyio
async def test_the_decorated_async_endpoint_drops_the_hidden_argument() -> None:
    api = Firewall("api")

    @api
    async def endpoint(value: str) -> str:
        return value

    # The framework passes the hidden dependency as a keyword; the wrapper drops it.
    hidden: dict[str, object] = {"_xtr_firewall_0": api}
    result: object = await endpoint("book", **hidden)

    assert result == "book"
