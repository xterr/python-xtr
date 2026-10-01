"""The IsGranted dependency, decorator form, and denial behaviour."""

from __future__ import annotations

import inspect

import pytest
from fastapi import HTTPException
from fastapi.params import Depends as DependsParam
from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.authorization import AccessDecisionManager
from xtr_security_core.exception import AccessDeniedError

from xtr_security_http.decorator.is_granted import IsGranted

pytestmark = pytest.mark.anyio


def test_it_is_a_dependency_marker() -> None:
    assert isinstance(IsGranted("ROLE_ADMIN"), DependsParam)


def test_it_records_its_attribute_and_options() -> None:
    marker = IsGranted("BOOK_EDIT", subject="isbn", message="no", status_code=418)

    assert marker.attribute == "BOOK_EDIT"
    assert marker.subject == "isbn"
    assert marker.message == "no"
    assert marker.status_code == 418


def test_the_dependency_reads_a_string_subject_from_a_path_param() -> None:
    dependency = IsGranted("X", subject="isbn").dependency
    assert dependency is not None

    assert "request" in inspect.signature(dependency).parameters


def test_a_callable_subject_becomes_a_sub_dependency() -> None:
    def load_book() -> str:
        return "book"

    dependency = IsGranted("X", subject=load_book).dependency
    assert dependency is not None

    assert "resolved" in inspect.signature(dependency).parameters


def test_it_decorates_an_endpoint_with_a_hidden_dependency() -> None:
    marker = IsGranted("ROLE_ADMIN")

    @marker
    async def endpoint() -> str:
        return "ok"

    parameters = inspect.signature(endpoint).parameters
    assert any(name.startswith("_xtr_is_granted_") for name in parameters)


def test_decorating_a_non_callable_returns_it_unchanged() -> None:
    marker = IsGranted("X")
    sentinel = object()

    assert marker(sentinel) is sentinel


async def test_a_denial_raises_access_denied() -> None:
    marker = IsGranted("ROLE_ADMIN")

    with pytest.raises(AccessDeniedError):
        await marker._decide(None, TokenStorage(), AccessDecisionManager([]))


async def test_a_denial_with_a_status_code_raises_http_exception() -> None:
    marker = IsGranted("ROLE_ADMIN", status_code=418, message="teapot")

    with pytest.raises(HTTPException) as caught:
        await marker._decide(None, TokenStorage(), AccessDecisionManager([]))

    assert caught.value.status_code == 418
