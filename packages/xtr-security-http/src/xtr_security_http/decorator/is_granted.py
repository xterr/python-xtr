"""The authorization dependency: require an attribute before an endpoint runs."""

from __future__ import annotations

import functools
import inspect
from typing import TYPE_CHECKING, Annotated, Final, ParamSpec, TypeVar, cast, overload

from fastapi import Depends
from fastapi.params import Depends as DependsParam

# The framework reads the dependency's signature at runtime to fill it from the
# container, so the injection marker, the request and the service types the
# resolver receives stay importable here.
from starlette.requests import Request  # noqa: TC002
from xtr_dependency_injection import Injected  # noqa: TC002
from xtr_security_core.authentication.token.null_token import NullToken
from xtr_security_core.authentication.token.storage.token_storage_interface import (  # noqa: TC002
    TokenStorageInterface,
)
from xtr_security_core.authorization.access_decision import AccessDecision
from xtr_security_core.authorization.access_decision_manager_interface import (  # noqa: TC002
    AccessDecisionManagerInterface,
)
from xtr_security_core.exception import AccessDeniedError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

__all__ = ["IsGranted"]

_P = ParamSpec("_P")
_R = TypeVar("_R")

_HIDDEN_PREFIX: Final = "_xtr_is_granted_"


class IsGranted(DependsParam):
    """Requires an attribute over a subject before the endpoint runs.

    Written as a dependency or a decorator:

    ```python
    @router.delete("/books/{isbn}")
    @IsGranted("ROLE_ADMIN")                          # below the route decorator
    async def delete_book(isbn: str) -> None: ...


    @router.put("/books/{isbn}", dependencies=[IsGranted("BOOK_EDIT", subject=load_book)])
    async def edit(book: Annotated[Book, Depends(load_book)]) -> Book: ...
    ```

    The attribute is a string a voter matches, or a callable
    ``(IsGrantedContext, subject) -> bool`` the closure voter runs. The subject
    is ``None``, the name of a path parameter, or a callable used as a FastAPI
    dependency — resolved once per request and shared with the endpoint. A
    denial raises an
    :class:`~xtr_security_core.exception.AccessDeniedError`, which the firewall's
    exception listener turns into ``401`` or ``403``; a ``status_code`` answers
    with that status directly instead. It requires a firewall to have run;
    without one the check is made against the anonymous token.

    The token storage and the access-decision manager the check reads are
    container-provided dependencies of the resolver, declared with
    :data:`~xtr_dependency_injection.Injected` — so the framework fills them from
    the request scope, never fetched from the container by hand.

    Attributes:
        attribute: The attribute required.
        subject: How the subject is obtained, or ``None``.
        message: The denial message.
        status_code: The status a denial answers with directly, or ``None``.
    """

    attribute: object  # pyright: ignore[reportUninitializedInstanceVariable]
    subject: object  # pyright: ignore[reportUninitializedInstanceVariable]
    message: str | None  # pyright: ignore[reportUninitializedInstanceVariable]
    status_code: int | None  # pyright: ignore[reportUninitializedInstanceVariable]

    def __init__(
        self,
        attribute: str | Callable[..., bool | Awaitable[bool]],
        subject: str | Callable[..., object] | None = None,
        *,
        message: str | None = None,
        status_code: int | None = None,
    ) -> None:
        """Require ``attribute`` over ``subject`` before the endpoint runs."""
        object.__setattr__(self, "attribute", attribute)
        object.__setattr__(self, "subject", subject)
        object.__setattr__(self, "message", message)
        object.__setattr__(self, "status_code", status_code)
        super().__init__(dependency=self._build(), use_cache=False)

    def _build(self) -> Callable[..., Awaitable[None]]:
        """Return the dependency function, wired to resolve the subject as FastAPI cares."""
        subject = self.subject
        if callable(subject):
            dependency = subject

            async def check_with_dependency(
                resolved: Annotated[object, Depends(dependency)],
                token_storage: Injected[TokenStorageInterface],
                access_decision_manager: Injected[AccessDecisionManagerInterface],
            ) -> None:
                await self._decide(resolved, token_storage, access_decision_manager)

            return check_with_dependency

        async def check(
            request: Request,
            token_storage: Injected[TokenStorageInterface],
            access_decision_manager: Injected[AccessDecisionManagerInterface],
        ) -> None:
            resolved = request.path_params.get(subject) if isinstance(subject, str) else None
            await self._decide(resolved, token_storage, access_decision_manager)

        return check

    async def _decide(
        self,
        subject: object,
        token_storage: TokenStorageInterface,
        access_decision_manager: AccessDecisionManagerInterface,
    ) -> None:
        """Decide the attribute over ``subject`` for the request's token.

        Raises:
            AccessDeniedError: When the attribute is not granted and no
                ``status_code`` was set.
            HTTPException: When the attribute is not granted and a
                ``status_code`` was set — answered with that status directly.
        """
        token = token_storage.get_token() or NullToken()
        decision = AccessDecision()
        granted = await access_decision_manager.decide(token, [self.attribute], subject, decision)
        if granted:
            return
        if self.status_code is not None:
            from fastapi import HTTPException  # noqa: PLC0415 -- http-only

            raise HTTPException(
                status_code=self.status_code,
                detail=self.message or "Access denied.",
            )
        raise AccessDeniedError(
            self.message or "Access Denied.",
            attributes=(self.attribute,),
            subject=subject,
            access_decision=decision,
        )

    @overload
    def __call__(self, target: Callable[_P, _R], /) -> Callable[_P, _R]: ...

    @overload
    def __call__(self, target: object, /) -> object: ...

    def __call__(self, target: Callable[_P, _R] | object, /) -> Callable[_P, _R] | object:
        """Attach this check to the endpoint ``target`` as a hidden dependency."""
        if not callable(target):
            return target
        endpoint = cast("Callable[_P, _R]", target)
        return self._decorate(endpoint)

    def _decorate(self, endpoint: Callable[_P, _R]) -> Callable[_P, _R]:
        """Return ``endpoint`` taking this check as a hidden dependency."""
        signature = inspect.signature(endpoint)
        taken = set(signature.parameters)
        index = 0
        while f"{_HIDDEN_PREFIX}{index}" in taken:
            index += 1
        name = f"{_HIDDEN_PREFIX}{index}"

        parameters = list(signature.parameters.values())
        keywords = [p for p in parameters if p.kind is inspect.Parameter.VAR_KEYWORD]
        others = [p for p in parameters if p.kind is not inspect.Parameter.VAR_KEYWORD]
        hidden = inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY, default=self)
        extended = signature.replace(parameters=[*others, hidden, *keywords])

        if inspect.iscoroutinefunction(endpoint):
            call = cast("Callable[_P, Awaitable[object]]", endpoint)

            @functools.wraps(endpoint)
            async def asynchronous(*args: _P.args, **kwargs: _P.kwargs) -> object:
                _ = kwargs.pop(name, None)
                return await call(*args, **kwargs)

            wrapper = cast("Callable[_P, _R]", asynchronous)
        else:

            @functools.wraps(endpoint)
            def synchronous(*args: _P.args, **kwargs: _P.kwargs) -> _R:
                _ = kwargs.pop(name, None)
                return endpoint(*args, **kwargs)

            wrapper = synchronous
        wrapper.__signature__ = extended  # pyright: ignore[reportAttributeAccessIssue]  # ty: ignore[unresolved-attribute]
        return wrapper
