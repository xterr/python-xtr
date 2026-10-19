"""The success answer a form login gives by default: back where the caller was heading.

A login that succeeds has one thing left to do — return the caller to what
they were doing — and where that is, is a ladder: the path the request
itself asked for under the configured parameter, then the path the
interrupted request saved on the session, then the page the caller came
from, then the configured default.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_http._parked_session import parked_session_of
from xtr_security_http._request_parameters import payload_parameter, query_parameter
from xtr_security_http.util import get_target_path, remove_target_path

from ._referer import names_login_or_current, referer_of
from .authentication_success_handler_interface import AuthenticationSuccessHandlerInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_logging_contracts import LoggerInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface

    from xtr_security_http.http_utils import HttpUtils

__all__ = ["DefaultAuthenticationSuccessHandler"]

#: The options a success answer is built from, and their defaults.
_DEFAULT_OPTIONS: dict[str, object] = {
    "always_use_default_target_path": False,
    "default_target_path": "/",
    "login_path": "/login",
    "target_path_parameter": "_target_path",
    "use_referer": False,
}


@final
class DefaultAuthenticationSuccessHandler(AuthenticationSuccessHandlerInterface):
    """Answers a successful login with a redirect, by the target ladder.

    The target is a ladder: the configured default, when the options say it
    always wins; a path the request carried under the configured parameter;
    the path the interrupted request saved on the session — read and removed,
    a return trip happens once; the page the caller came from, when the
    options ask for it; then the configured default.
    """

    __slots__ = ("_firewall_name", "_http_utils", "_logger", "_options")

    def __init__(
        self,
        http_utils: HttpUtils,
        options: Mapping[str, object] | None = None,
        logger: LoggerInterface | None = None,
    ) -> None:
        """Record the URI machinery, the options and the logger.

        Args:
            http_utils: Matches paths and builds the redirect, so the
                handler names neither a response nor a URI class.
            options: The options the wiring collected, merged over the
                defaults.
            logger: Logs a parameter the ladder ignored, when one is given.
        """
        self._http_utils = http_utils
        self._logger = logger
        self._firewall_name: str | None = None
        self._options: dict[str, object] = {}
        self.set_options(options or {})

    def get_options(self) -> dict[str, object]:
        """Return every option the handler answers from."""
        return dict(self._options)

    def set_options(self, options: Mapping[str, object]) -> None:
        """Merge ``options`` over the defaults, and answer from the merge."""
        self._options = {**_DEFAULT_OPTIONS, **options}

    def get_firewall_name(self) -> str | None:
        """Return the firewall whose login this handler answers, when one is set."""
        return self._firewall_name

    def set_firewall_name(self, firewall_name: str) -> None:
        """Record ``firewall_name``, keying the session's saved target path."""
        self._firewall_name = firewall_name

    @override
    async def on_authentication_success(
        self,
        request: ServerRequestInterface,
        token: TokenInterface,
    ) -> ResponseInterface | None:
        """Answer with a redirect to the target the ladder picks."""
        del token
        return self._http_utils.create_redirect_response(
            request,
            await self._determine_target_url(request),
        )

    async def _determine_target_url(self, request: ServerRequestInterface) -> str:
        """Return the URL the success redirect answers with, by the ladder."""
        if self._options["always_use_default_target_path"]:
            return str(self._options["default_target_path"])
        asked = await self._asked_target_of(request)
        if asked is not None:
            return asked
        saved = await self._saved_target_of(request)
        if saved is not None:
            return saved
        referer = await self._referer_target_of(request)
        if referer is not None:
            return referer
        return str(self._options["default_target_path"])

    async def _asked_target_of(self, request: ServerRequestInterface) -> str | None:
        """Return the path the request carried under the configured parameter.

        A path that is not a path at all — not an absolute path, not an
        absolute URL — is ignored with a note, and the ladder goes on.
        """
        parameter = str(self._options["target_path_parameter"])
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
        return None

    async def _saved_target_of(self, request: ServerRequestInterface) -> str | None:
        """Return the path the interrupted request saved on the session, and remove it.

        A return trip happens once: the saved path is the page the caller
        was heading for when the login interrupted them, and once they are
        back on it, it is not a place to return to again.
        """
        if self._firewall_name is None:
            return None
        session = parked_session_of(request)
        if session is None:
            return None
        kept = await get_target_path(session, self._firewall_name)
        if kept is None:
            return None
        await remove_target_path(session, self._firewall_name)
        return kept

    async def _referer_target_of(self, request: ServerRequestInterface) -> str | None:
        """Return the page the caller came from, when the options ask for it.

        The two pages that must never win are set aside: the login page —
        the caller is coming *from* it — and the page the request asked for,
        which is not a return trip but a repetition.
        """
        if not self._options["use_referer"]:
            return None
        referer = referer_of(request)
        if referer is None:
            return None
        if names_login_or_current(request, referer, str(self._options["login_path"])):
            return None
        return referer
