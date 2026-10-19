"""What the last login attempt left, for the page that renders the form again.

A failed form login parks its error and the username it was asked for, so
the page that renders the form a second time can explain the failure and
re-fill the identifier field. Where each is read from follows one rule: the
request's own security state first — what the flow parked on it — then the
session, which is where a login that answered with a redirect leaves them.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import TYPE_CHECKING, cast, final

from xtr_security_core.exception import AuthenticationError

from xtr_security_http._parked_session import parked_session_of
from xtr_security_http._security_state import security_state_of
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["AuthenticationUtils"]


@final
class AuthenticationUtils:
    """Reads the last login attempt's error and username off one request.

    A login page builds one over the request it is rendering, and reads
    three things: the error to explain, the username to re-fill, and — when
    the request is asking a caller who is already authenticated to prove
    themselves again — which attribute that proof is being asked for.
    """

    __slots__ = ("_request",)

    def __init__(self, request: ServerRequestInterface) -> None:
        """Read the login form's answers off ``request``."""
        self._request = request

    async def get_last_authentication_error(
        self,
        clear_session: bool = True,
    ) -> AuthenticationError | None:
        """Return the error the last login attempt failed with, when one was kept.

        The request's own state is read first — a failure the flow is still
        answering is parked there — and the session second, which is where a
        login that redirected back to its form leaves the error for the page
        that renders it. Reading it off the session takes it away again
        unless ``clear_session`` is ``False``: an error page shows an error
        once, not on every reload.

        Args:
            clear_session: Whether the error read off the session is removed
                with it, so a reload of the page shows no stale error.
        """
        error = self._state_attributes().get(SecurityRequestAttributes.AUTHENTICATION_ERROR)
        if isinstance(error, AuthenticationError):
            return error
        session = parked_session_of(self._request)
        if session is None or not await session.has(SecurityRequestAttributes.AUTHENTICATION_ERROR):
            return None
        kept = await session.get(SecurityRequestAttributes.AUTHENTICATION_ERROR)
        if clear_session:
            _ = await session.remove(SecurityRequestAttributes.AUTHENTICATION_ERROR)
        return kept if isinstance(kept, AuthenticationError) else None

    async def get_last_username(self) -> str:
        """Return the username the last login attempt carried, for the form to re-fill.

        The request's own state is read first, the session second, and a
        request that kept no username answers with the empty string — the
        form renders with an empty field, not with a missing one.
        """
        username = self._state_attributes().get(SecurityRequestAttributes.LAST_USERNAME)
        if isinstance(username, str):
            return username
        session = parked_session_of(self._request)
        if session is not None:
            kept = await session.get(SecurityRequestAttributes.LAST_USERNAME)
            if isinstance(kept, str):
                return kept
        return ""

    async def get_re_authentication_attribute(self) -> str | None:
        """Return the attribute a re-authentication is being asked for, when one is.

        Reading it does not end the re-authentication — a successful login
        does, by removing the attribute — so the page still knows what it is
        asking for when the user mistypes their password. The request's own
        attribute is read first, then the session, where the entry point that
        started the re-authentication keeps it across the redirect.
        """
        attribute = self._request.get_attribute(
            SecurityRequestAttributes.RE_AUTHENTICATION_ATTRIBUTE,
        )
        if isinstance(attribute, str):
            return attribute
        session = parked_session_of(self._request)
        if session is not None:
            kept = await session.get(SecurityRequestAttributes.RE_AUTHENTICATION_ATTRIBUTE)
            if isinstance(kept, str):
                return kept
        return None

    def _state_attributes(self) -> MutableMapping[str, object]:
        """Return the attributes the request's security state carries.

        A request no stateful machinery ran for carries no state at all, and
        reads as carrying nothing — every lookup misses, which is the honest
        answer for a request the flow never touched.
        """
        bag = self._request.get_attribute(SecurityRequestAttributes.STATE_BAG)
        if not isinstance(bag, MutableMapping):
            return {}
        return security_state_of(cast("MutableMapping[str, object]", bag)).attributes
