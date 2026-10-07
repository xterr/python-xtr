"""The firewall dependency: attach it to an app, a router or a route."""

from __future__ import annotations

import functools
import inspect
from typing import TYPE_CHECKING, Final, ParamSpec, TypeVar, cast, overload

from fastapi import APIRouter
from fastapi.params import Security

from xtr_security_http.firewall_scheme import FirewallScheme

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterable

__all__ = ["Firewall"]

_P = ParamSpec("_P")
_R = TypeVar("_R")

_HIDDEN_PREFIX: Final = "_xtr_firewall_"


class Firewall(Security):
    """A firewall a request passes before its endpoint runs.

    Written wherever the framework takes a dependency, as a decorator, or on a
    router before its routes:

    ```python
    app = FastAPI(dependencies=[Firewall()])       # chosen per request by the config
    api = Firewall("api")                            # bound by name: exact OpenAPI scheme

    router = APIRouter(prefix="/api", dependencies=[api])


    @router.get("/books", dependencies=[api.scoped("books:read")])
    async def books() -> list[Book]: ...


    @router.delete("/books/{isbn}")
    @Firewall("api")                                 # below the route decorator
    async def delete_book(isbn: str) -> None: ...
    ```

    Bound by name, it resolves that firewall directly and shows its exact
    scheme in OpenAPI. Unbound, it is matched per request to the first firewall
    whose request matcher claims it. Authentication runs once per request
    however many firewall dependencies a route carries; the accumulated
    ``scopes`` are checked against the token with the OAuth2 scope voter.

    Attributes:
        firewall_name: The firewall bound by name, or ``None`` when matched per
            request.
    """

    firewall_name: str | None  # pyright: ignore[reportUninitializedInstanceVariable]

    def __init__(
        self,
        name: str | None = None,
        *,
        scopes: Iterable[str] = (),
        _scheme: FirewallScheme | None = None,
    ) -> None:
        """Attach the firewall ``name`` (or the matched one), requiring ``scopes``.

        Args:
            name: The firewall to bind by name, or ``None`` to match per request.
            scopes: The scopes a request must carry, added to the OpenAPI
                operation and checked by the scope voter.
            _scheme: The shared scheme a scoped variant reuses; not for callers.
        """
        scheme = _scheme if _scheme is not None else FirewallScheme(name)
        super().__init__(dependency=scheme, scopes=list(scopes), use_cache=True)
        object.__setattr__(self, "firewall_name", name)

    def scoped(self, *scopes: str) -> Firewall:
        """Return a variant requiring ``scopes``, sharing this firewall's scheme.

        The returned firewall points at the same scheme object, so the two are
        one security scheme in OpenAPI with the scopes added to the operation
        that uses the variant. Named ``scoped`` — not ``scopes`` — because the
        framework reads ``scopes`` as the accumulated list on the marker itself.
        """
        scheme = cast("FirewallScheme", self.dependency)
        return Firewall(self.firewall_name, scopes=scopes, _scheme=scheme)

    @overload
    def __call__(self, target: APIRouter, /) -> APIRouter: ...

    @overload
    def __call__(self, target: Callable[_P, _R], /) -> Callable[_P, _R]: ...

    def __call__(self, target: APIRouter | Callable[_P, _R], /) -> APIRouter | Callable[_P, _R]:
        """Attach this firewall to every route of ``target``, or to the endpoint ``target``.

        A router must have no route yet — the framework copies a router's
        dependencies into each route as it is added. An endpoint must be
        decorated below its route decorator, which reads the endpoint's
        signature then.
        """
        if isinstance(target, APIRouter):
            target.dependencies.append(self)
            return target
        return self._decorate(target)

    def _decorate(self, endpoint: Callable[_P, _R]) -> Callable[_P, _R]:
        """Return ``endpoint`` taking this firewall as a hidden dependency."""
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
