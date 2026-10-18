"""The service that decides an attribute over a subject before an endpoint runs."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from fastapi import HTTPException
from xtr_security_core.authentication.token.null_token import NullToken
from xtr_security_core.authentication.token.storage.token_storage_interface import (  # noqa: TC002 -- the container reads this constructor parameter's type at runtime
    TokenStorageInterface,
)
from xtr_security_core.authorization.access_decision import AccessDecision
from xtr_security_core.authorization.access_decision_manager_interface import (  # noqa: TC002 -- the container reads this constructor parameter's type at runtime
    AccessDecisionManagerInterface,
)
from xtr_security_core.exception import AccessDeniedError

from xtr_security_http.authorization.oauth2_scope_voter import oauth2_scope

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_http.decorator.is_granted import IsGranted

__all__ = ["IsGrantedChecker"]


@final
class IsGrantedChecker:
    """Decides a route's attribute over its subject, through the voters.

    The route marker —
    :class:`~xtr_security_http.decorator.is_granted.IsGranted` — states what
    must be granted and how a denial answers; this service runs that statement
    through the access-decision machinery, so the deciding lives in one place —
    testable without the web framework, and reusable behind any other
    enforcement mechanism.

    The decision is made against the request's token, or the anonymous token
    when no firewall ran. A denial raises
    :class:`~xtr_security_core.exception.AccessDeniedError` carrying the
    attribute, the subject and the decision — answered ``403`` by the
    firewall's exception listener — or, when the marker states a
    ``status_code``, an :class:`HTTPException` answering with that status
    directly.

    The security scopes a route declared natively are **ignored** unless the
    marker opted in: ``consume_security_scopes`` on the marker turns each
    accumulated scope into an ``oauth2_scope(...)`` attribute the voter stack
    must grant, one by one; without it, scopes stay what declaring them alone
    ever makes them — documentation.
    """

    __slots__ = ("_access_decision_manager", "_token_storage")

    def __init__(
        self,
        token_storage: TokenStorageInterface,
        access_decision_manager: AccessDecisionManagerInterface,
    ) -> None:
        """Build the checker over the request's storage and the decision manager.

        Args:
            token_storage: Holds the token the firewall authenticated for
                this request.
            access_decision_manager: Decides the attribute over the subject.
        """
        self._token_storage = token_storage
        self._access_decision_manager = access_decision_manager

    async def check(
        self,
        is_granted: IsGranted,
        subject: object = None,
        *,
        security_scopes: Sequence[str] = (),
    ) -> None:
        """Decide ``is_granted``'s attribute over ``subject``, denying when it fails.

        Args:
            is_granted: The route marker stating the attribute and how a
                denial answers.
            subject: The subject the attribute is decided over.
            security_scopes: The request's accumulated security scopes, each
                decided as an ``oauth2_scope(...)`` attribute the voters must
                grant — passed only where the marker opted in.

        Raises:
            AccessDeniedError: When the attribute (or an opted-in scope) is
                not granted and the marker states no ``status_code``.
            HTTPException: When the attribute is not granted and the marker
                states a ``status_code`` — answered with that status.
        """
        token = self._token_storage.get_token() or NullToken()
        decision = AccessDecision()
        granted = await self._access_decision_manager.decide(
            token,
            [is_granted.attribute],
            subject,
            decision,
        )
        for scope in security_scopes:
            if not await self._access_decision_manager.decide(
                token,
                [oauth2_scope(scope)],
                None,
                decision,
            ):
                granted = False
                break
        decision.is_granted = granted
        if granted:
            return
        if is_granted.status_code is not None:
            raise HTTPException(
                status_code=is_granted.status_code,
                detail=is_granted.message or "Access denied.",
            )
        raise AccessDeniedError(
            is_granted.message or "Access Denied.",
            attributes=(is_granted.attribute,),
            subject=subject,
            access_decision=decision,
        )
