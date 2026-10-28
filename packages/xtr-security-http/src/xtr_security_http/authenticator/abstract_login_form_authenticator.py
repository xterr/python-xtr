"""A base for the authenticators a user logs in through by submitting a form.

Everything a form login shares is here: the URL of the page the form lives
on, the request the form is submitted by — a POST to exactly that page —
and the two answers that send the caller back to it: a failed login's
redirect, and the entry point's redirect when a protected page was reached
without logging in at all.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar
from urllib.parse import unquote

from typing_extensions import override

from xtr_security_http._parked_session import parked_session_of
from xtr_security_http.entry_point.authentication_entry_point_interface import (
    AuthenticationEntryPointInterface,
)
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

from .abstract_authenticator import AbstractAuthenticator
from .debug.unsupported_reasons import UnsupportedReasons
from .interactive_authenticator_interface import InteractiveAuthenticatorInterface

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.exception import AuthenticationError

    from xtr_security_http.http_utils import HttpUtils

__all__ = ["AbstractLoginFormAuthenticator"]


class AbstractLoginFormAuthenticator(  # pyright: ignore[reportImplicitAbstractClass] -- get_login_url stays abstract
    AbstractAuthenticator,
    AuthenticationEntryPointInterface,
    InteractiveAuthenticatorInterface,
):
    """The parts every form-login authenticator shares.

    A subclass names its login page's URL — :meth:`get_login_url`, the one
    abstract part — and reads the submitted form into a passport. The
    request the form is submitted by is decided here: a POST whose path is
    exactly the login page's, compared strictly, so the URL the subclass
    names must be a path; a subclass that builds an absolute one overrides
    :meth:`supports` too.

    A failed login keeps its error for the page that renders the form again
    and returns the caller to the login page; a protected page reached
    without logging in is redirected there by the entry point this class
    also is. And the login is the user's own act — announced as one,
    through the interactive-login event.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_http_utils",)

    def __init__(self, http_utils: HttpUtils) -> None:
        """Record the URI machinery that builds this login's redirects.

        Args:
            http_utils: Builds the redirect responses, so the class names no
                response class.
        """
        self._http_utils: HttpUtils = http_utils

    def get_login_url(self, request: ServerRequestInterface) -> str:
        """Return the URL of the login page — abstract here, concrete in a subclass.

        The default :meth:`supports` compares this value, as it is returned,
        with the request's path, so it must be a path (``/login``); a
        subclass that builds an absolute URL overrides :meth:`supports` too.
        """
        del request
        raise NotImplementedError("A form-login authenticator must implement get_login_url.")

    @override
    def supports(self, request: ServerRequestInterface) -> bool:
        """Handle the request only when it is the form's submission.

        A POST whose path is exactly the login page's — the comparison is
        strict, so :meth:`get_login_url` must return a path — is the form's
        submission; anything else is not, and says why when the tooling is
        listening.
        """
        reasons = request.get_attribute(SecurityRequestAttributes.UNSUPPORTED_REASONS)
        if request.get_method() != "POST":
            if isinstance(reasons, UnsupportedReasons):
                reasons.add(
                    f'the request method is "{request.get_method()}", and only POST is supported',
                )
            return False
        login_url = self.get_login_url(request)
        path = unquote(request.get_uri().get_path())
        if login_url != path:
            if isinstance(reasons, UnsupportedReasons):
                reasons.add(f'the request path "{path}" does not match the login URL "{login_url}"')
            return False
        return True

    @override
    async def on_authentication_failure(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError,
    ) -> ResponseInterface | None:
        """Keep the error for the form that renders again, and return to the login page.

        The error is kept on the request's session — the one place the
        redirect's target and the page that renders it share — under the
        key a login page reads through
        :class:`~xtr_security_http.authentication.authentication_utils.AuthenticationUtils`.
        """
        session = parked_session_of(request)
        if session is not None:
            await session.set(SecurityRequestAttributes.AUTHENTICATION_ERROR, error)
        return self._http_utils.create_redirect_response(request, self.get_login_url(request))

    @override
    async def start(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError | None = None,
    ) -> ResponseInterface:
        """Redirect the caller to the login page.

        The error that led here needs no explaining on the form: the caller
        never submitted one, so there is nothing to explain yet.
        """
        del error
        return self._http_utils.create_redirect_response(request, self.get_login_url(request))

    @override
    def is_interactive(self) -> bool:
        """Announce the login as the user's own act: a form is submitted by hand."""
        return True
