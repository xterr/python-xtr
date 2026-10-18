"""The IsGranted marker: metadata, dependency shape, and decorator form."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, cast, final

import pytest
from fastapi.params import Depends as DependsParam
from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.authentication.token.username_password_token import UsernamePasswordToken
from xtr_security_core.authorization import AccessDecisionManager, RoleVoter
from xtr_security_core.exception import AccessDeniedError
from xtr_security_core.user.in_memory_user import InMemoryUser

from xtr_security_http.decorator.is_granted import IsGranted
from xtr_security_http.resolver.is_granted_checker import IsGrantedChecker

if TYPE_CHECKING:
    from collections.abc import Sequence

    from fastapi import Request

pytestmark = pytest.mark.anyio


def test_it_is_a_dependency_marker() -> None:
    assert isinstance(IsGranted("ROLE_ADMIN"), DependsParam)


def test_it_records_its_attribute_and_options() -> None:
    marker = IsGranted(
        "BOOK_EDIT",
        subject="isbn",
        message="no",
        status_code=418,
        exception_code=0x17,
        methods=["PUT", "get"],
        consume_security_scopes=True,
    )

    assert marker.attribute == "BOOK_EDIT"
    assert marker.subject == "isbn"
    assert marker.message == "no"
    assert marker.status_code == 418
    assert marker.exception_code == 0x17
    assert marker.methods == ("PUT", "GET", "HEAD")
    assert marker.consume_security_scopes is True


def test_a_get_method_extends_to_head() -> None:
    assert IsGranted("X", methods="GET").methods == ("GET", "HEAD")


def test_no_methods_apply_to_every_one() -> None:
    assert IsGranted("X").methods == ()


def test_the_dependency_reads_the_request_and_delegates_to_the_checker() -> None:
    dependency = IsGranted("X", subject="isbn").dependency
    assert dependency is not None

    parameters = inspect.signature(dependency).parameters

    assert "request" in parameters
    assert "checker" in parameters
    assert "security_scopes" in parameters
    assert cast("object", parameters["security_scopes"].annotation) == "SecurityScopes"


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


async def test_a_denial_raises_access_denied_through_the_checker() -> None:
    checker = IsGrantedChecker(TokenStorage(), AccessDecisionManager([RoleVoter()]))

    with pytest.raises(AccessDeniedError):
        await checker.check(IsGranted("ROLE_ADMIN"))


async def test_a_granted_attribute_passes_through_the_checker() -> None:
    storage = TokenStorage()
    storage.set_token(
        UsernamePasswordToken(InMemoryUser("root", roles=["ROLE_ADMIN"]), "api", ["ROLE_ADMIN"]),
    )
    checker = IsGrantedChecker(storage, AccessDecisionManager([RoleVoter()]))

    await checker.check(IsGranted("ROLE_ADMIN"))


@final
class _RecordingChecker:
    """Stands in for the injected checker, recording the scopes it was handed."""

    def __init__(self) -> None:
        self.scopes: tuple[str, ...] = ()

    async def check(
        self,
        is_granted: IsGranted,
        subject: object = None,
        *,
        security_scopes: Sequence[str] = (),
    ) -> None:
        """Record the scopes instead of deciding; the scopes are what the test reads."""
        del is_granted, subject
        self.scopes = tuple(security_scopes)


@final
class _Request:
    """The request surface ``_check`` reads: the method alone."""

    method = "GET"


async def test_the_accumulated_scopes_are_ignored_unless_the_marker_opts_in() -> None:
    """The D12b rule: scopes are never consumed without the marker's explicit opt-in."""
    checker = _RecordingChecker()

    # The fakes stand in for the injected checker and the framework's request;
    # the recorded scopes are what the test reads, not the types they stand in for.
    request = cast("Request", cast("object", _Request()))
    injected = cast("IsGrantedChecker", cast("object", checker))

    await IsGranted("ROLE_ADMIN")._check(injected, request, None, ("books:write",))

    assert checker.scopes == ()

    opted_in = IsGranted("ROLE_ADMIN", consume_security_scopes=True)

    await opted_in._check(injected, request, None, ("books:write",))

    assert checker.scopes == ("books:write",)
