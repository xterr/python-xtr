"""The marker that requires a valid cross-site request forgery token."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast, final

from fastapi import Request  # noqa: TC002 -- the framework reads this annotation at runtime
from fastapi.params import Depends as DependsParam

# The framework reads the dependency's signature at runtime to fill it from the
# container, so the injection marker and the checker type stay importable here.
from xtr_dependency_injection import Injected  # noqa: TC002

from xtr_security_http.resolver.csrf_token_checker import CsrfTokenChecker  # noqa: TC001

from ._methods import normalized_methods

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = ["IsCsrfTokenValid"]

SOURCE_PAYLOAD: Final = 0b0001
"""Read the presented value from the request payload: the JSON body, else the form."""

SOURCE_QUERY: Final = 0b0010
"""Read the presented value from the query string."""

SOURCE_HEADER: Final = 0b0100
"""Read the presented value from a header."""


@final
class IsCsrfTokenValid(DependsParam):
    """Requires the request to present the value minted for a token id.

    Used as a dependency or a decorator, like
    :class:`~xtr_security_http.decorator.is_granted.IsGranted`. The marker is
    pure metadata — which token id a route proves, where the request carries
    the value, which methods it applies to — and the checking happens in the
    injectable
    :class:`~xtr_security_http.resolver.csrf_token_checker.CsrfTokenChecker`
    the thin dependency delegates to, which hands the presented value to the
    token manager.

    A request that presents no value, or one the manager does not vouch for,
    is refused with a ``403``. The sources are a bitmask: the default reads
    the payload (the JSON body, else the parsed form); ``SOURCE_QUERY`` and
    ``SOURCE_HEADER`` widen it, and several combine — the first source named
    that carries a value wins. A marker that names no method applies to every
    one; a marker that names ``GET`` also answers ``HEAD``.

    Attributes:
        token_id: The id the token is known under — what it guards.
        token_key: The key the request carries the value under.
        methods: The (upper-cased) methods the check applies to; empty is all.
        token_source: The bitmask of the sources the value is read from.
    """

    token_id: str  # pyright: ignore[reportUninitializedInstanceVariable]
    token_key: str  # pyright: ignore[reportUninitializedInstanceVariable]
    methods: tuple[str, ...]  # pyright: ignore[reportUninitializedInstanceVariable]
    token_source: int  # pyright: ignore[reportUninitializedInstanceVariable]

    def __init__(
        self,
        token_id: str,
        *,
        token_key: str = "_token",  # noqa: S107 -- a form key name, not a credential
        methods: str | Sequence[str] = (),
        token_source: int = SOURCE_PAYLOAD,
    ) -> None:
        """Require the value minted for ``token_id``, read as ``token_source`` says."""
        object.__setattr__(self, "token_id", token_id)
        object.__setattr__(self, "token_key", token_key)
        object.__setattr__(self, "methods", normalized_methods(methods))
        object.__setattr__(self, "token_source", token_source)
        super().__init__(dependency=self._check, use_cache=False)

    async def _check(self, request: Request, checker: Injected[CsrfTokenChecker]) -> None:
        """Refuse the request unless it presents the value minted for the token id.

        Raises:
            HTTPException: ``403`` — when the method applies and the request
                presents no value, or one the manager does not vouch for.
        """
        if self.methods and request.method.upper() not in self.methods:
            return
        await checker.check(self, await _token_value(request, self.token_source, self.token_key))


async def _token_value(request: Request, token_source: int, token_key: str) -> str | None:
    """Read the presented value from the first source the bitmask names that has one."""
    if token_source & SOURCE_PAYLOAD:
        value = await _payload_value(request, token_key)
        if value is not None:
            return value
    if token_source & SOURCE_QUERY:
        value = request.query_params.get(token_key)
        if value is not None:
            return value
    if token_source & SOURCE_HEADER:
        return request.headers.get(token_key)
    return None


async def _payload_value(request: Request, token_key: str) -> str | None:
    """Read the value from the request payload: the JSON body, else the parsed form."""
    try:
        payload = cast("object", await request.json())
    except ValueError:
        # A body that is not JSON is not an error: the form is the payload then.
        payload = None
    if isinstance(payload, dict):
        value = cast("Mapping[str, object]", payload).get(token_key)
        return value if isinstance(value, str) else None
    form = await request.form()
    value = cast("object", form.get(token_key))
    return value if isinstance(value, str) else None
