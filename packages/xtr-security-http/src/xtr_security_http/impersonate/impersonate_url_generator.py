"""Generating the impersonation and exit paths, URLs and forms."""

from __future__ import annotations

from typing import TYPE_CHECKING, final
from urllib.parse import urlencode, urlsplit

from xtr_security_core.authentication.token.storage.token_storage_interface import (  # noqa: TC002
    TokenStorageInterface,
)
from xtr_security_core.authentication.token.switch_user_token import SwitchUserToken

from xtr_security_http.exception import ImpersonationError
from xtr_security_http.firewall.switch_user_listener import SwitchUserListener

from .impersonation_form import ImpersonationForm

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_csrf.csrf_token_manager_interface import CsrfTokenManagerInterface

    from .switch_user_config_lookup_interface import SwitchUserConfigLookupInterface

__all__ = ["ImpersonateUrlGenerator"]


def _csrf_field_of(csrf_parameter: str | None, fields: dict[str, str]) -> str | None:
    """Return the forgery field's name among ``fields``, or ``None`` when none is."""
    if csrf_parameter is not None and csrf_parameter in fields:
        return csrf_parameter
    return None


def _plain_path(path: str, request: ServerRequestInterface | None) -> str:
    """Return ``path`` as it is: the URI of a path is the path.

    The default URI builder. A ``Location`` header may carry a path, and
    the framework resolves it against the request's own host; an
    application that wants absolute URLs injects a builder that writes
    them, reading the request the address is generated against.
    """
    del request
    return path


def _is_absolute_url(path: str) -> bool:
    """Tell whether ``path`` already is an absolute URL."""
    split = urlsplit(path)
    return split.scheme != "" and split.netloc != ""


def _request_uri_of(request: ServerRequestInterface) -> str:
    """Return the request's own URI: its path, and its query when it carries one."""
    uri = request.get_uri()
    query = uri.get_query()
    return f"{uri.get_path()}?{query}" if query else uri.get_path()


@final
class ImpersonateUrlGenerator:
    """Provides the impersonation and exit paths, URLs and forms of a firewall.

    Asked for the address a switch to a user — or the exit from one — is
    started by, the generator reads how the request's firewall asks for
    switches and writes the address: the page the request is at, carrying
    the switch's parameter, or the firewall's dedicated path when it has
    one. The exit addresses answer empty while the current user
    impersonates nobody, so a template can skip them.

    The request is a parameter of every method, where the upstream stack
    reads it from a request stack this kernel does not have; and the
    firewall's switch configuration is read through the lookup the
    generator is built with, where the upstream generator reaches into
    the bundle's own firewall map — the recorded deviations.

    A path is always a literal path — an absolute path (``/switch``) or
    an absolute URL (``https://…``) — never a route name: this stack has
    no routing component to resolve one by, the recorded deviation. The
    URI a path becomes in the URL methods is written by the injected URI
    builder — the path itself by default, an absolute URL when the
    application's builder writes one.
    """

    __slots__ = ("_config_lookup", "_csrf_token_manager", "_token_storage", "_uri_builder")

    def __init__(
        self,
        config_lookup: SwitchUserConfigLookupInterface,
        token_storage: TokenStorageInterface,
        uri_builder: Callable[[str, ServerRequestInterface | None], str] | None = None,
        csrf_token_manager: CsrfTokenManagerInterface | None = None,
    ) -> None:
        """Record the lookup, the storage and the builders the generation reads.

        Args:
            config_lookup: Answers the switch-user configuration of the
                firewall a request runs in.
            token_storage: Read to tell whether the current user is
                impersonating anyone, which the exit addresses stand on.
            uri_builder: Writes the absolute URI a path becomes in the
                URL methods. Left out, a path is its own URI — a
                ``Location`` may carry one, and the framework resolves it
                against the request's host.
            csrf_token_manager: Mints the token a generated address
                carries, when the firewall's switch asks for one.
        """
        self._config_lookup = config_lookup
        self._token_storage = token_storage
        self._uri_builder = _plain_path if uri_builder is None else uri_builder
        self._csrf_token_manager = csrf_token_manager

    async def generate_impersonation_path(
        self,
        request: ServerRequestInterface,
        identifier: str,
        target_uri: str | None = None,
    ) -> str:
        """Generate the path a switch to ``identifier`` is started by."""
        url, parameters, _ = await self._parts(request, target_uri, identifier)
        return self._with_query(url, parameters)

    async def generate_impersonation_url(
        self,
        request: ServerRequestInterface,
        identifier: str,
        target_uri: str | None = None,
    ) -> str:
        """Generate the absolute URL a switch to ``identifier`` is started by."""
        url, parameters, _ = await self._parts(request, target_uri, identifier)
        return self._with_query(self._absolute(url, request), parameters)

    async def generate_exit_path(
        self,
        request: ServerRequestInterface,
        target_uri: str | None = None,
    ) -> str:
        """Generate the path an exit from the current switch is asked by."""
        url, parameters, _ = await self._parts(request, target_uri)
        return self._with_query(url, parameters)

    async def generate_exit_url(
        self,
        request: ServerRequestInterface,
        target_uri: str | None = None,
    ) -> str:
        """Generate the absolute URL an exit from the current switch is asked by."""
        url, parameters, _ = await self._parts(request, target_uri)
        return self._with_query(self._absolute(url, request), parameters)

    async def generate_impersonation_form(
        self,
        request: ServerRequestInterface,
        identifier: str,
        target_uri: str | None = None,
    ) -> ImpersonationForm:
        """Return the action and the hidden fields of a form triggering the switch.

        Unlike the URLs, this keeps the parameters out of the address bar
        and works with a path restricted to ``POST`` requests. The fields
        hold the identifier of the user to switch to, the page to come
        back to on a dedicated path, and the forgery token when the
        switch asks for one.
        """
        action, fields, csrf_parameter = await self._parts(request, target_uri, identifier)
        return ImpersonationForm(
            action=action,
            fields=fields,
            csrf_field=_csrf_field_of(csrf_parameter, fields),
        )

    async def generate_exit_form(
        self,
        request: ServerRequestInterface,
        target_uri: str | None = None,
    ) -> ImpersonationForm:
        """Return the action and the hidden fields of a form exiting the switch.

        The action is empty when the current user is not impersonating
        anyone, so that a template can skip the form.
        """
        action, fields, csrf_parameter = await self._parts(request, target_uri)
        return ImpersonationForm(
            action=action,
            fields=fields,
            csrf_field=_csrf_field_of(csrf_parameter, fields),
        )

    def _is_impersonated(self) -> bool:
        """Tell whether the current user is impersonating another one."""
        return isinstance(self._token_storage.get_token(), SwitchUserToken)

    async def _parts(
        self,
        request: ServerRequestInterface,
        target_uri: str | None,
        identifier: str = SwitchUserListener.EXIT_VALUE,
    ) -> tuple[str, dict[str, str], str | None]:
        """Build the address, its parameters and its forgery field name.

        Returns:
            The address itself — the page the request is at, or the
            firewall's dedicated path — the parameters the switch is
            asked by, and the name of the forgery parameter among them,
            or ``None`` when the switch asks for no token.

        Raises:
            ImpersonationError: When the request's firewall has no user
                switch, when its switch asks for a forgery token while no
                manager was given, or when its dedicated path is a route
                name, which no routing component here can resolve.
        """
        if not self._is_impersonated() and identifier == SwitchUserListener.EXIT_VALUE:
            return "", {}, None
        config = await self._config_lookup.get_switch_user_config(request)
        if config is None:
            raise ImpersonationError(
                "Unable to generate the impersonate URLs without a firewall configured "
                "for the user switch.",
            )
        parameters = {config.parameter: identifier}
        csrf_parameter: str | None = None
        if config.enable_csrf:
            if self._csrf_token_manager is None:
                raise ImpersonationError(
                    "Unable to generate the impersonate URLs without a CSRF token manager.",
                )
            # The token id is served by the manager the firewall configured for it.
            csrf_parameter = config.csrf_parameter
            parameters[csrf_parameter] = (
                await self._csrf_token_manager.get_token(config.csrf_token_id)
            ).get_value()
        if config.path is not None:
            # The switch happens on a dedicated endpoint, so the page to
            # come back to is carried explicitly.
            parameters["_target_path"] = (
                target_uri if target_uri is not None else _request_uri_of(request)
            )
            if not config.path.startswith("/"):
                raise ImpersonationError(
                    f"The switch path {config.path!r} is not an absolute path; route names "
                    "are not supported, only literal paths.",
                )
            return config.path, parameters, csrf_parameter
        url = target_uri if target_uri is not None else _request_uri_of(request)
        return url, parameters, csrf_parameter

    def _absolute(self, path: str, request: ServerRequestInterface) -> str:
        """Return ``path`` as the absolute URI the URL methods carry.

        An absolute URL is returned as it is; anything else goes through
        the URI builder — the path itself while none is injected.
        """
        if _is_absolute_url(path):
            return path
        return self._uri_builder(path, request)

    @staticmethod
    def _with_query(url: str, parameters: dict[str, str]) -> str:
        """Return ``url`` beside ``parameters`` as its query string."""
        if not parameters or url == "":
            return url
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}{urlencode(parameters)}"
