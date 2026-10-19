"""The failure answer a form login gives by default: back to the login page.

A login that fails has one honest thing to say — "try again" — and one
place to say it: the login page. Where exactly that is, is a ladder: the
path the request itself asked for under the configured parameter, then the
configured failure path, then the login page. Before the redirect, the
error is kept for the page that renders the form again, and — when the
caller came from a page of the application's own — that page is kept as
the return trip's target.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_security_core.exception import InvalidArgumentError

from xtr_security_http._parked_session import parked_session_of
from xtr_security_http._request_parameters import payload_parameter, query_parameter
from xtr_security_http.security_request_attributes import SecurityRequestAttributes
from xtr_security_http.util import get_target_path, save_target_path

from ._referer import names_login_or_current, names_request_host, referer_of
from .authentication_failure_handler_interface import AuthenticationFailureHandlerInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_logging_contracts import LoggerInterface
    from xtr_security_core.exception import AuthenticationError

    from xtr_security_http.http_utils import HttpUtils

__all__ = ["DefaultAuthenticationFailureHandler"]

#: The options a failure answer is built from, and their defaults. The
#: ``failure_path`` of ``None`` means "the login page".
_DEFAULT_OPTIONS: dict[str, object] = {
    "failure_path": None,
    "failure_forward": False,
    "login_path": "/login",
    "failure_path_parameter": "_failure_path",
    "use_referer": False,
    "always_use_default_target_path": False,
}


@final
class DefaultAuthenticationFailureHandler(AuthenticationFailureHandlerInterface):
    """Answers a failed login with a redirect, keeping the error for the form.

    The redirect target is a ladder: a path the request carried under the
    configured parameter — a query parameter a page with a login form of its
    own sets — then the configured failure path, then the login page. The
    error is kept on the request's session for the page that renders the
    form again, and the page the caller came from is kept as the return
    trip's target when the options ask for it.

    The ``failure_forward`` option is refused: this stack has no sub-request
    to hand the login page to, so the redirect is the only path an answer
    takes. A configuration that asks for the forward is a wiring mistake to
    report, not a request to answer.
    """

    __slots__ = ("_firewall_name", "_http_utils", "_logger", "_options")

    def __init__(
        self,
        http_utils: HttpUtils,
        options: Mapping[str, object] | None = None,
        logger: LoggerInterface | None = None,
        firewall_name: str | None = None,
    ) -> None:
        """Record the URI machinery, the options, the logger and the firewall's name.

        Args:
            http_utils: Matches paths and builds the redirect, so the
                handler names neither a response nor a URI class.
            options: The options the wiring collected, merged over the
                defaults.
            logger: Logs the redirect that answers, when one is given.
            firewall_name: The firewall that failed to authenticate, keying
                the return trip's target so two firewalls never overwrite
                each other's.
        """
        self._http_utils = http_utils
        self._logger = logger
        self._firewall_name = firewall_name
        self._options: dict[str, object] = {}
        self.set_options(options or {})

    def get_options(self) -> dict[str, object]:
        """Return every option the handler answers from."""
        return dict(self._options)

    def set_options(self, options: Mapping[str, object]) -> None:
        """Merge ``options`` over the defaults, and answer from the merge."""
        self._options = {**_DEFAULT_OPTIONS, **options}

    @override
    async def on_authentication_failure(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError,
    ) -> ResponseInterface:
        """Answer with a redirect, keeping the error for the form that renders again."""
        if self._options["failure_forward"]:
            raise InvalidArgumentError(
                "The failure_forward option is not supported: no sub-request exists to "
                "forward the login page to, so the redirect is the only answer.",
            )
        await self._keep_referer_target(request)
        failure_path = self._failure_path_of(request)
        if self._logger is not None:
            self._logger.debug(
                "Authentication failure, redirect triggered.",
                {"failure_path": failure_path},
            )
        session = parked_session_of(request)
        if session is not None:
            await session.set(SecurityRequestAttributes.AUTHENTICATION_ERROR, error)
        return self._http_utils.create_redirect_response(request, failure_path)

    async def _keep_referer_target(self, request: ServerRequestInterface) -> None:
        """Keep the page the caller came from as the return trip's target.

        Only when the options ask for it, the handler knows its firewall,
        and no target is kept yet: a target the flow already kept — the
        protected page that sent the caller to the login — is the better
        word of where they were heading, and is not overwritten by where
        they happened to come from. The referer must name a page of the
        application's own host, and neither the login page nor the page the
        request asked for — the first is where the caller already is, the
        second is what sent them to the login.
        """
        if not self._options["use_referer"] or self._options["always_use_default_target_path"]:
            return
        if self._firewall_name is None:
            return
        session = parked_session_of(request)
        if session is None or await get_target_path(session, self._firewall_name) is not None:
            return
        referer = referer_of(request)
        if referer is None or not names_request_host(request, referer):
            return
        login_path = self._options["login_path"]
        if names_login_or_current(request, referer, str(login_path)):
            return
        await save_target_path(session, self._firewall_name, referer)

    def _failure_path_of(self, request: ServerRequestInterface) -> str:
        """Return the path the failure redirect answers with, by the ladder.

        A path the request carried under the configured parameter wins when
        it is a path at all — an absolute path or an absolute URL — and is
        ignored with a note when it is not; then the configured failure
        path, then the login page.
        """
        parameter = str(self._options["failure_path_parameter"])
        asked = query_parameter(request, parameter)
        if asked is None:
            asked = payload_parameter(request, parameter)
        if isinstance(asked, str) and asked.startswith(("/", "http")):
            return asked
        if self._logger is not None and asked:
            self._logger.debug(
                "Ignoring query parameter {parameter!r}: not a valid URL.",
                {"parameter": parameter},
            )
        failure_path = self._options["failure_path"]
        if isinstance(failure_path, str) and failure_path:
            return failure_path
        return str(self._options["login_path"])
