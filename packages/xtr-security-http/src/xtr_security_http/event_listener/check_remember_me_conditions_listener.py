"""The listener that decides whether a successful login asked to be remembered."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_event_dispatcher import EventSubscriberInterface

from xtr_security_http._request_parameters import payload_parameter, query_parameter
from xtr_security_http.authenticator.passport.badge.remember_me_badge import RememberMeBadge
from xtr_security_http.event.login_success_event import LoginSuccessEvent

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_event_dispatcher import SubscribedEvents
    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_logging_contracts import LoggerInterface

__all__ = ["CheckRememberMeConditionsListener"]

#: The options the conditions are checked with, and their defaults: the
#: application never asks and the request says so with the form's checkbox.
_DEFAULT_OPTIONS: Mapping[str, object] = {
    "always_remember_me": False,
    "remember_me_parameter": "_remember_me",
}

#: The spellings a request parameter may ask to be remembered with — the
#: same ones a boolean form field is read by. Anything else reads as no.
_REMEMBERED_SPELLINGS = ("1", "true", "on", "yes")


@final
class CheckRememberMeConditionsListener(EventSubscriberInterface):
    """Enables the remember-me badge when a login asked for the cookie.

    Three conditions, and only together do they earn a cookie: the passport
    carries the badge — the authenticator knows a login may be remembered —
    the firewall configured the feature — this listener runs — and the
    login asked for it, either because the application always wants the
    cookie or because the request carried the remember-me parameter. The
    parameter is read where a submitted form carries it and the query string
    second, and the badge's own parameters are read first, so an
    authenticator that already knows the answer — a login link, a token
    login — states it there.

    Runs before the listener that sets the cookie, so the badge it enables
    is the one that listener reads.
    """

    __slots__ = ("_logger", "_options")

    def __init__(
        self,
        options: Mapping[str, object] | None = None,
        logger: LoggerInterface | None = None,
    ) -> None:
        """Record the options the conditions are checked with, and the logger.

        Args:
            options: ``always_remember_me`` — the application wants the
                cookie for every login — and ``remember_me_parameter`` — the
                name the request carries its ask under; merged over the
                defaults.
            logger: Where the decision is logged, or ``None``.
        """
        self._options: dict[str, object] = {**_DEFAULT_OPTIONS, **(options or {})}
        self._logger = logger

    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        """Listen to a successful login, ahead of the listener that sets the cookie."""
        return {LoginSuccessEvent: ("on_login_success", -32)}

    async def on_login_success(self, event: LoginSuccessEvent) -> None:
        """Enable the badge when the login asked to be remembered.

        A passport without the badge is a login through an authenticator
        that never offered remembering — nothing to enable. With the badge,
        the ask is checked: always, or the request's parameter.
        """
        badge = event.get_passport().get_badge(RememberMeBadge)
        if badge is None:
            return
        if self._options["always_remember_me"] is not True:
            parameter = _remember_me_parameter(
                event.get_request(),
                str(self._options["remember_me_parameter"]),
                badge.get_parameters(),
            )
            if not _asks_to_be_remembered(parameter):
                if self._logger is not None:
                    self._logger.debug(
                        "Remember me disabled; request does not contain remember me "
                        'parameter ("{parameter}").',
                        {"parameter": self._options["remember_me_parameter"]},
                    )
                return
        _ = badge.enable()


def _remember_me_parameter(
    request: ServerRequestInterface,
    name: str,
    badge_parameters: Mapping[str, object],
) -> object | None:
    """Read the remember-me ask: the badge's own word first, then the request's.

    The badge's parameters outrank the request — an authenticator that
    states the ask itself is not overruled by a form that carries none. The
    request is read where a submitted form carries a field and the query
    string second; a body is not read for a ``GET`` or a ``HEAD``, which
    carry no form to read.
    """
    value = badge_parameters.get(name)
    if value is not None:
        return value
    value = request.get_attribute(name)
    if value is not None:
        return value
    value = query_parameter(request, name)
    if value is not None:
        return value
    if request.get_method() in ("GET", "HEAD"):
        return None
    return payload_parameter(request, name)


def _asks_to_be_remembered(value: object | None) -> bool:
    """Tell whether ``value`` is one of the spellings that ask to be remembered.

    The boolean spellings a form field is read by: ``1``, ``true``, ``on``
    and ``yes``, read without regard to case, and the booleans and the one
    integer themselves. Everything else — an empty field, a ``0``, a word
    the list does not know — reads as no ask.
    """
    match value:
        case bool():
            return value
        case int():
            return value == 1
        case str():
            return value.lower() in _REMEMBERED_SPELLINGS
        case _:
            return False
