"""The authorization dependency: require an attribute before an endpoint runs."""

from __future__ import annotations

import functools
import inspect
from typing import TYPE_CHECKING, Annotated, Final, ParamSpec, TypeVar, cast, overload

from fastapi import Depends, Request
from fastapi.params import Depends as DependsParam
from fastapi.security import (
    SecurityScopes,  # noqa: TC002 -- the framework reads this annotation at runtime
)

# The framework reads the dependency's signature at runtime to fill it from the
# container, so the injection marker and the checker type stay importable here.
from xtr_dependency_injection import Injected  # noqa: TC002

from xtr_security_http.resolver.is_granted_checker import IsGrantedChecker  # noqa: TC001

from ._methods import normalized_methods

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

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

    The marker is pure metadata — what must be granted, over what, and how a
    denial answers — and the deciding happens in the injectable
    :class:`~xtr_security_http.resolver.is_granted_checker.IsGrantedChecker`
    the thin dependency delegates to, which runs the attribute through the
    access-decision machinery.

    The attribute is a string a voter matches, or a callable
    ``(IsGrantedContext, subject) -> bool`` the closure voter runs. The subject
    is ``None``, the name of a path parameter, or a callable used as a FastAPI
    dependency — resolved once per request and shared with the endpoint. A
    denial raises an
    :class:`~xtr_security_core.exception.AccessDeniedError`, which the firewall's
    exception listener turns into ``401`` or ``403``; a ``status_code`` answers
    with that status directly instead. It requires a firewall to have run;
    without one the check is made against the anonymous token.

    ``methods`` limits the check to those (upper-cased; ``GET`` extends to
    ``HEAD``); a marker that names none applies to every method. The security
    scopes a route declared natively are **ignored** unless
    ``consume_security_scopes=True``: opted in, the request's accumulated
    scopes are decided through the voter stack too, each one an attribute that
    must be granted; without it they stay declaration and documentation, and
    adding this marker to a chain never silently turns them into enforcement.

    Attributes:
        attribute: The attribute required.
        subject: How the subject is obtained, or ``None``.
        message: The denial message.
        status_code: The status a denial answers with directly, or ``None``.
        exception_code: A code recorded on the marker for the caller that
            catches the denial.
        methods: The (upper-cased) methods the check applies to; empty is all.
        consume_security_scopes: Whether the request's accumulated security
            scopes are decided too.
    """

    attribute: object  # pyright: ignore[reportUninitializedInstanceVariable]
    subject: object  # pyright: ignore[reportUninitializedInstanceVariable]
    message: str | None  # pyright: ignore[reportUninitializedInstanceVariable]
    status_code: int | None  # pyright: ignore[reportUninitializedInstanceVariable]
    exception_code: int | None  # pyright: ignore[reportUninitializedInstanceVariable]
    methods: tuple[str, ...]  # pyright: ignore[reportUninitializedInstanceVariable]
    consume_security_scopes: bool  # pyright: ignore[reportUninitializedInstanceVariable]

    def __init__(  # noqa: PLR0913 -- the marker's metadata surface mirrors the upstream attribute
        self,
        attribute: str | Callable[..., bool | Awaitable[bool]],
        subject: str | Callable[..., object] | None = None,
        *,
        message: str | None = None,
        status_code: int | None = None,
        exception_code: int | None = None,
        methods: str | Sequence[str] = (),
        consume_security_scopes: bool = False,
    ) -> None:
        """Require ``attribute`` over ``subject`` before the endpoint runs."""
        object.__setattr__(self, "attribute", attribute)
        object.__setattr__(self, "subject", subject)
        object.__setattr__(self, "message", message)
        object.__setattr__(self, "status_code", status_code)
        object.__setattr__(self, "exception_code", exception_code)
        object.__setattr__(self, "methods", normalized_methods(methods))
        object.__setattr__(self, "consume_security_scopes", consume_security_scopes)
        super().__init__(dependency=self._build(), use_cache=False)

    def _build(self) -> Callable[..., Awaitable[None]]:
        """Return the dependency function, wired to resolve the subject as the framework cares."""
        subject = self.subject
        if callable(subject):
            dependency = subject

            async def check_with_dependency(
                resolved: Annotated[object, Depends(dependency)],
                request: Request,
                checker: Injected[IsGrantedChecker],
                security_scopes: SecurityScopes,
            ) -> None:
                await self._check(checker, request, resolved, security_scopes.scopes)

            return check_with_dependency

        async def check(
            request: Request,
            checker: Injected[IsGrantedChecker],
            security_scopes: SecurityScopes,
        ) -> None:
            resolved = request.path_params.get(subject) if isinstance(subject, str) else None
            await self._check(checker, request, resolved, security_scopes.scopes)

        return check

    async def _check(
        self,
        checker: IsGrantedChecker,
        request: Request,
        subject: object,
        security_scopes: Sequence[str],
    ) -> None:
        """Decide this marker over ``subject``, on the methods it applies to."""
        if self.methods and request.method.upper() not in self.methods:
            return
        await checker.check(
            self,
            subject,
            security_scopes=security_scopes if self.consume_security_scopes else (),
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
