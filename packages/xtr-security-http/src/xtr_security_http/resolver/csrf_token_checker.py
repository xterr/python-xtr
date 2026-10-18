"""The service that checks a presented cross-site request forgery token."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from fastapi import HTTPException
from xtr_dependency_injection import remove_if_missing
from xtr_security_csrf.csrf_token import CsrfToken
from xtr_security_csrf.csrf_token_manager_interface import (
    CsrfTokenManagerInterface,
)

if TYPE_CHECKING:
    from xtr_security_http.decorator.is_csrf_token_valid import IsCsrfTokenValid

__all__ = ["CsrfTokenChecker"]


@final
@remove_if_missing(service=CsrfTokenManagerInterface)
class CsrfTokenChecker:
    """Checks the token a request presents against the value stored for its id.

    The route marker —
    :class:`~xtr_security_http.decorator.is_csrf_token_valid.IsCsrfTokenValid`
    — states which token id a route proves and where the request carries the
    value; this service hands the presented value to the token manager, which
    compares it with what it stored when the page was rendered. A request
    that presents no value, or one the manager does not vouch for, is refused
    with a ``403``: the caller is already identified, so a missing or wrong
    proof is a forbidden request, not a challenge to authenticate.

    The service is registered only where a token manager is: without one
    wired, the definition is dropped, so an application that ships no
    cross-site request forgery storage never builds a checker that cannot
    answer.
    """

    __slots__ = ("_csrf_token_manager",)

    def __init__(self, csrf_token_manager: CsrfTokenManagerInterface) -> None:
        """Build the checker over the manager that mints and vouches for tokens.

        Args:
            csrf_token_manager: Compares a presented token value with the
                value stored under its id.
        """
        self._csrf_token_manager = csrf_token_manager

    async def check(
        self,
        is_csrf_token_valid: IsCsrfTokenValid,
        token_value: str | None,
    ) -> None:
        """Vouch for the value a request presented under the marker's token id.

        Raises:
            HTTPException: ``403`` — when the request presented no value, or
                one the manager does not vouch for.
        """
        if token_value is None or not await self._csrf_token_manager.is_token_valid(
            CsrfToken(is_csrf_token_valid.token_id, token_value),
        ):
            raise HTTPException(status_code=403, detail="Invalid CSRF token.")
