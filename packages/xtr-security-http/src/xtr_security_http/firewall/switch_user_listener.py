"""The chain step that switches the user a request asks to impersonate."""

# One flow, one file: the switch, the exit and the answer are the step's own
# single responsibility, and the per-firewall constructor the upstream shape
# fixes is most of the bulk. (allow: SIZE_OK — one chain step, one flow, a
# 16-argument per-firewall constructor mirroring the upstream one.)

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_http_kernel.bridge import Response as FrameworkResponse
from xtr_http_kernel.bridge import (
    StarletteHttpFactoryInterface,
)
from xtr_logging_contracts import NullLogger
from xtr_security_core.authentication.token.storage.token_storage_interface import (  # noqa: TC002
    TokenStorageInterface,
)
from xtr_security_core.authentication.token.switch_user_token import SwitchUserToken
from xtr_security_core.authorization.access_decision import AccessDecision
from xtr_security_core.exception import (
    AccessDeniedError,
    AuthenticationCredentialsNotFoundError,
    AuthenticationError,
    InvalidArgumentError,
)
from xtr_security_core.user.user_interface import UserInterface
from xtr_security_csrf.csrf_token import CsrfToken

from xtr_security_http._security_state import security_state_of, state_bag_of
from xtr_security_http.decorator.firewall_listener_order import FirewallListenerOrder
from xtr_security_http.event.switch_user_event import SwitchUserEvent
from xtr_security_http.security_events import SecurityEvents
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

from ._switch_load import load_user_timing_equalised
from ._switch_request import request_parameter_of, switch_username_of
from ._switch_uri import uri_without_parameters
from .abstract_listener import AbstractListener
from .authenticator_manager_listener import AuthenticatorManagerListener

if TYPE_CHECKING:
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_kernel.event.request_event import RequestEvent
    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_logging_contracts import LoggerInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.authorization.access_decision_manager_interface import (
        AccessDecisionManagerInterface,
    )
    from xtr_security_core.user.user_checker_interface import UserCheckerInterface
    from xtr_security_core.user.user_provider_interface import UserProviderInterface
    from xtr_security_csrf.csrf_token_manager_interface import CsrfTokenManagerInterface

    from xtr_security_http.http_utils import HttpUtils

__all__ = ["SwitchUserListener"]


@final
@FirewallListenerOrder(after=AuthenticatorManagerListener)
class SwitchUserListener(AbstractListener):
    """Lets a user temporarily act as another one, like the ``su`` command.

    A chain step for a firewall configured with a user switch. ``supports``
    answers whether the request is asking for a switch — it carries the
    configured parameter naming the user to become — and ``authenticate``
    carries the switch out: the request proves itself first, when a
    cross-site request forgery manager is wired, then the right to switch
    is decided — the configured role, against the target user as the
    subject — and the target user is loaded, checked, and settled on a
    token that keeps the way back. The request is answered with a
    redirect to the page it was asked at, the switch's own parameters
    stripped from the address.

    The exit is the same parameter carrying the exit value: the original
    token the switch started from is restored, its user reloaded first,
    and the request redirected the same way. A user already switched may
    switch again — the current switch is left seamlessly before the new
    one begins — and asking for the user already impersonated changes
    nothing.

    The load of the target user is timing-equalised: a second, throwaway
    identifier no provider can know is loaded beside it, and a target
    that cannot be loaded burns a load of the current user instead, so
    the time a switch takes never tells whether a user exists.
    """

    EXIT_VALUE: Final[str] = "_exit"
    """The parameter value that asks to leave an impersonation, not start one."""

    __slots__ = (
        "_access_decision_manager",
        "_bridge",
        "_csrf_parameter",
        "_csrf_token_id",
        "_csrf_token_manager",
        "_dispatcher",
        "_firewall_name",
        "_http_utils",
        "_logger",
        "_path",
        "_provider",
        "_role",
        "_stateless",
        "_token_storage",
        "_user_checker",
        "_username_parameter",
    )

    def __init__(  # noqa: PLR0913, PLR0917 -- the per-firewall shape: one step built from its firewall's parts, mirroring the upstream constructor
        self,
        token_storage: TokenStorageInterface,
        provider: UserProviderInterface,
        user_checker: UserCheckerInterface,
        firewall_name: str,
        access_decision_manager: AccessDecisionManagerInterface,
        bridge: StarletteHttpFactoryInterface,
        http_utils: HttpUtils,
        logger: LoggerInterface | None = None,
        username_parameter: str = "_switch_user",
        role: str = "ROLE_ALLOWED_TO_SWITCH",
        dispatcher: EventDispatcherInterface | None = None,
        stateless: bool = False,
        path: str | None = None,
        csrf_token_manager: CsrfTokenManagerInterface | None = None,
        csrf_parameter: str = "_csrf_token",
        csrf_token_id: str = "switch_user",  # noqa: S107 -- the default id of the switch's forgery token, not a credential
    ) -> None:
        """Build the step over one firewall's switch parts.

        Args:
            token_storage: The request's token storage, read for the token
                to switch from and written with the token a switch settles
                on.
            provider: Loads the user a switch asks to become.
            user_checker: Checks the target user's account state once the
                switch is decided.
            firewall_name: The firewall the switch happens in, recorded on
                the switched token.
            access_decision_manager: Decides the right to switch — the
                configured role, against the target user as the subject.
            bridge: Turns the redirect into what the lifecycle's event
                accepts — the kernel's rule for messages from elsewhere.
            http_utils: Builds the redirect, and matches the request's
                path when the switch is scoped to one. The upstream step
                takes its HTTP utilities optionally and builds its
                redirect directly; here they are the one redirect builder
                — the class names no response class — so both are
                required.
            logger: Writes the switch's decisions, when given.
            username_parameter: The name a request carries the user to
                switch to under.
            role: The role the right to switch is decided by.
            dispatcher: Where the switch event is announced, when given.
            stateless: Leaves the request unanswered — no redirect — for a
                firewall that keeps no session.
            path: The dedicated path a switch is asked at, or ``None`` to
                read the parameter on any page.
            csrf_token_manager: Vouches for the token a switch request
                presents, or ``None`` while the firewall asks for no proof.
            csrf_parameter: The name a request carries the forgery token
                under.
            csrf_token_id: The id the forgery token is stored under.

        Raises:
            InvalidArgumentError: When ``firewall_name`` is empty.
        """
        if firewall_name == "":
            raise InvalidArgumentError('The "firewall_name" must not be empty.')
        self._token_storage = token_storage
        self._provider = provider
        self._user_checker = user_checker
        self._firewall_name = firewall_name
        self._access_decision_manager = access_decision_manager
        self._bridge = bridge
        self._http_utils = http_utils
        self._logger = logger or NullLogger()
        self._username_parameter = username_parameter
        self._role = role
        self._dispatcher = dispatcher
        self._stateless = stateless
        self._path = path
        self._csrf_token_manager = csrf_token_manager
        self._csrf_parameter = csrf_parameter
        self._csrf_token_id = csrf_token_id

    @override
    async def supports(self, request: ServerRequestInterface) -> bool:
        """Answer whether ``request`` is asking for a user switch.

        Scoped to a dedicated path, only a request both at that path and
        carrying the parameter asks; on any page, the parameter alone
        asks, wherever the request carries it. The username it names is
        parked on the request's security state for ``authenticate``.
        """
        if self._path is not None:
            if not self._http_utils.check_request_path(request, self._path):
                return False
            username = request_parameter_of(request, self._username_parameter)
            if not isinstance(username, str):
                username = None
        else:
            username = switch_username_of(request, self._username_parameter)
        if username is None or username == "":
            return False
        security_state_of(state_bag_of(request)).attributes[
            SecurityRequestAttributes.SWITCH_USER_USERNAME
        ] = username
        return True

    @override
    async def authenticate(self, request_event: RequestEvent) -> None:
        """Carry the switch out, and answer with a redirect to the page it was asked at.

        Raises:
            AccessDeniedError: When a wired forgery token does not check
                out, the right to switch is refused, or the switch itself
                failed — the last always as a plain refusal, so a failed
                switch never tells whether a user exists.
            AuthenticationCredentialsNotFoundError: When no token is held
                to switch from, or an exit is asked with no switch to leave.
        """
        request = request_event.request
        state = security_state_of(request_event.state)
        parked = state.attributes.pop(SecurityRequestAttributes.SWITCH_USER_USERNAME, None)
        if not isinstance(parked, str):
            # Nothing parked means no supports pass ran — the request asked
            # for no switch, and this step is not the one that ran.
            return
        await self._prove_the_request(request)
        if self._token_storage.get_token() is None:
            raise AuthenticationCredentialsNotFoundError("Could not find original Token object.")
        if parked == self.EXIT_VALUE:
            _ = await self._attempt_exit_user(request)
        else:
            try:
                self._token_storage.set_token(await self._attempt_switch_user(request, parked))
            except AuthenticationError as error:
                # Refuse in any conditions, so a failed switch cannot
                # enumerate users by its error or its timing.
                raise AccessDeniedError(f"Switch User failed: {error}") from error
        if self._stateless:
            return
        await self._answer(request_event, request)

    async def _attempt_switch_user(
        self,
        request: ServerRequestInterface,
        username: str,
    ) -> TokenInterface:
        """Switch to ``username``, and return the token the switch settles on.

        Raises:
            AccessDeniedError: When the configured role is not granted for
                the target user.
        """
        token = self._token_storage.get_token()
        if token is None:
            # The entry already refused a request with no token; a storage
            # emptied since answers the same way.
            raise AuthenticationCredentialsNotFoundError("Could not find original Token object.")
        original_token = self._original_token_of(token)
        if original_token is not None:
            if token.get_user_identifier() == username:
                return token
            # Already switched: leave the current switch before seamlessly
            # switching to another user.
            token = await self._attempt_exit_user(request)
        current_username = token.get_user_identifier()
        user = await load_user_timing_equalised(self._provider, username, current_username)
        decision = AccessDecision()
        granted = await self._access_decision_manager.decide(
            token,
            (self._role,),
            subject=user,
            access_decision=decision,
        )
        if not granted:
            raise AccessDeniedError(
                "Switching user is not allowed.",
                attributes=(self._role,),
                access_decision=decision,
            )
        self._logger.info("Attempting to switch to user.", {"username": username})
        await self._user_checker.check_post_auth(user, token)
        roles = user.get_roles()
        originated_from_uri = uri_without_parameters(
            str(request.get_uri()),
            (self._username_parameter,),
        )
        token = SwitchUserToken(user, self._firewall_name, roles, token, originated_from_uri)
        if self._dispatcher is not None:
            switch_event = SwitchUserEvent(request, user, token)
            _ = await self._dispatcher.dispatch(switch_event, SecurityEvents.SWITCH_USER)
            # Use the token from the event in case any listeners have replaced it.
            replaced = switch_event.get_token()
            if replaced is not None:
                token = replaced
        return token

    async def _attempt_exit_user(self, request: ServerRequestInterface) -> TokenInterface:
        """Leave the current switch, restoring and returning the original token.

        The original user is reloaded first — a switch returns to the user
        as they are now, not as the switch began — and the switch event is
        announced for the exit too, where a listener may replace the token
        restored.

        Raises:
            AuthenticationCredentialsNotFoundError: When no switch is held
                to leave.
        """
        current_token = self._token_storage.get_token()
        original = self._original_token_of(current_token)
        if current_token is None or original is None:
            raise AuthenticationCredentialsNotFoundError("Could not find original Token object.")
        original_user = original.get_user()
        if self._dispatcher is not None and isinstance(original_user, UserInterface):
            user = await self._provider.refresh_user(original_user)
            original.set_user(user)
            switch_event = SwitchUserEvent(request, user, original)
            _ = await self._dispatcher.dispatch(switch_event, SecurityEvents.SWITCH_USER)
            replaced = switch_event.get_token()
            if replaced is not None:
                original = replaced
        self._token_storage.set_token(original)
        return original

    async def _prove_the_request(self, request: ServerRequestInterface) -> None:
        """Check the forgery token a switch request presents, when one is wired.

        Raises:
            AccessDeniedError: When the request presents no token value, or
                one the manager does not vouch for.
        """
        manager = self._csrf_token_manager
        if manager is None:
            return
        value = request_parameter_of(request, self._csrf_parameter)
        if not isinstance(value, str) or not await manager.is_token_valid(
            CsrfToken(self._csrf_token_id, value),
        ):
            raise AccessDeniedError("Invalid CSRF token.")

    async def _answer(
        self,
        request_event: RequestEvent,
        request: ServerRequestInterface,
    ) -> None:
        """Answer the request with a redirect to the page the switch returns to.

        On a dedicated path there is no current page to return to, so the
        submitted target path is honoured, or the root; elsewhere the
        request's own URI is, the switch's parameters stripped from it.
        The upstream stack can also redirect to a configured target route;
        no routing component exists here, so that fallback is not taken,
        the recorded deviation.
        """
        if self._path is not None:
            target = request_parameter_of(request, "_target_path")
            if not isinstance(target, str) or not target.startswith("/"):
                target = "/"
        else:
            parameters = (self._username_parameter,)
            if self._csrf_token_manager is not None:
                # Keep the token out of the address bar, the history, the
                # logs and the Referer of the landing page.
                parameters = (self._username_parameter, self._csrf_parameter)
            target = uri_without_parameters(str(request.get_uri()), parameters)
        response = self._http_utils.create_redirect_response(request, target)
        if isinstance(response, FrameworkResponse):
            request_event.set_response(response)
            return
        request_event.set_response(await self._bridge.create_response(response))

    @staticmethod
    def _original_token_of(token: TokenInterface | None) -> TokenInterface | None:
        """Return the token ``token``'s switch started from, or ``None``."""
        if isinstance(token, SwitchUserToken):
            return token.get_original_token()
        return None
