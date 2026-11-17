"""Who the request ran as, under which firewall, and what was decided about it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast, final

from xtr_http_kernel.data_collector import RequestTrace, clone_var
from xtr_security_core import Access, SwitchUserToken
from xtr_security_http import SecurityRequestAttributes
from xtr_security_http._security_state import SecurityState

from ._masking import masked

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_kernel.data_collector import ProfiledRequest
    from xtr_security_core import TokenInterface
    from xtr_security_http import TraceableAuthenticator
    from xtr_security_http.firewall_context_interface import FirewallContextInterface

__all__ = ["SecurityDataCollector"]

_NAME: Final = "security"


@final
class SecurityDataCollector:
    """Keeps the firewall, the token, the authenticators tried and the access decisions.

    The firewall and the token are read off the request's security state as
    the response starts: the firewall parked its context there and the access
    step the token it decided with. Decisions and authenticators are recorded
    while the request runs — the traceable decision manager and the traceable
    manager listener report to :meth:`record_decision` and
    :meth:`record_authenticator` — into traces of the request being served,
    which :meth:`begin_request` starts as a profiled request arrives; they are
    read once the response has left, so an authenticator's outcome and a
    decision made while the body streamed are in.

    Both are recorded only where tracing decorated them — ``votes_traced`` and
    ``authenticators_traced`` say whether it did, so the panel tells "none
    made" from "not traced". Nothing a credential is kept in is recorded: the
    token's credentials are never read, and a passport or a subject keeps
    ``******`` under every name like a password's, a secret's or a token's.
    """

    __slots__ = ("_authenticators", "_authenticators_traced", "_decisions", "_votes_traced")

    def __init__(self, *, votes_traced: bool, authenticators_traced: bool) -> None:
        """Record decisions and authenticators, telling which of them tracing reports.

        Args:
            votes_traced: Whether the decision manager reports its decisions.
            authenticators_traced: Whether the firewalls' authenticators
                report what they did.
        """
        self._votes_traced = votes_traced
        self._authenticators_traced = authenticators_traced
        self._decisions: RequestTrace[dict[str, object]] = RequestTrace("security_decisions")
        self._authenticators: RequestTrace[TraceableAuthenticator] = RequestTrace(
            "security_authenticators"
        )

    @property
    def name(self) -> str:
        """``"security"``."""
        return _NAME

    def begin_request(self) -> None:
        """Start recording the decisions and authenticators of the request that just arrived."""
        self._decisions.begin()
        self._authenticators.begin()

    def record_decision(self, entry: Mapping[str, object]) -> None:
        """Keep a finished decision, as plain data, when a profiled request is being recorded.

        Turned into plain data at once, so the subject is shown as it was when
        decided; outside a profiled request nothing is cloned.
        """
        if self._decisions.is_recording():
            self._decisions.record(_decision(entry))

    def record_authenticator(self, authenticator: TraceableAuthenticator) -> None:
        """Keep an authenticator the firewall asked, read once it has answered."""
        self._authenticators.record(authenticator)

    def collect(self, profiled: ProfiledRequest) -> dict[str, object]:
        """Return the firewall and the token the request ran under."""
        state = profiled.state.get(SecurityRequestAttributes.SECURITY_STATE)
        security = state if isinstance(state, SecurityState) else None
        context = security.firewall_context if security is not None else None
        return {
            "enabled": context is not None,
            "firewall": _firewall(context) if context is not None else None,
            "token": _token(security.token) if security is not None else None,
            "votes_traced": self._votes_traced,
            "authenticators_traced": self._authenticators_traced,
        }

    def late_collect(self, data: dict[str, object], profiled: ProfiledRequest) -> dict[str, object]:
        """Return the decisions and the authenticators the request recorded."""
        del profiled
        decisions = self._decisions.entries()
        return {
            **data,
            "decisions": list(decisions),
            "voter_strategy": decisions[-1]["strategy"] if decisions else None,
            "authenticators": [_authenticator(each) for each in self._authenticators.entries()],
        }


def _firewall(context: FirewallContextInterface) -> dict[str, object]:
    return {
        "name": context.name,
        "security": context.security,
        "entry_point": _class_of(context.entry_point),
        "access_denied_handler": _class_of(context.access_denied_handler),
        "listeners": [_qualified(type(listener)) for listener in context.listeners],
        "logout": context.logout_listener is not None,
    }


def _token(token: TokenInterface | None) -> dict[str, object] | None:
    if token is None:
        return None
    original = token.get_original_token() if isinstance(token, SwitchUserToken) else None
    return {
        "class": _qualified(type(token)),
        "user_identifier": token.get_user_identifier(),
        "roles": list(token.get_role_names()),
        "authenticated": token.get_user() is not None,
        "impersonated": original is not None,
        "impersonator": original.get_user_identifier() if original is not None else None,
    }


def _decision(entry: Mapping[str, object]) -> dict[str, object]:
    result = entry.get("result")
    strategy = entry.get("strategy")
    voters = cast("list[Mapping[str, object]]", entry.get("voter_details", []))
    return {
        "attributes": _attributes(entry.get("attributes", ())),
        "subject": masked(clone_var(entry.get("object"), max_depth=1)),
        "result": result if isinstance(result, bool) else None,
        "strategy": strategy if isinstance(strategy, str) else None,
        "voters": [
            {
                "voter": _qualified(type(voter.get("voter"))),
                "attributes": _attributes(voter.get("attributes", ())),
                "vote": _vote(voter.get("vote")),
                "reasons": [str(reason) for reason in cast("tuple[object, ...]", voter["reasons"])],
            }
            for voter in voters
        ],
    }


def _authenticator(authenticator: TraceableAuthenticator) -> dict[str, object]:
    info = authenticator.get_info()
    supports = info.get("supports")
    authenticated = info.get("authenticated")
    duration = info.get("duration")
    passport = info.get("passport")
    error = info.get("exception")
    return {
        "authenticator": _qualified(type(authenticator.get_authenticator())),
        "supports": supports if isinstance(supports, bool) else None,
        "unsupported_reasons": [
            str(reason) for reason in cast("tuple[object, ...]", info["unsupported_reasons"])
        ],
        "authenticated": authenticated if isinstance(authenticated, bool) else None,
        "duration_ms": duration * 1000.0 if isinstance(duration, float) else None,
        "passport": masked(clone_var(passport, max_depth=1)) if passport is not None else None,
        "error": (str(error) or type(error).__qualname__) if error is not None else None,
        "error_class": _qualified(type(error)) if error is not None else None,
    }


def _attributes(attributes: object) -> list[str]:
    """Name each attribute: as written when it is text, by its qualified name when callable."""
    return [_attribute(attribute) for attribute in cast("tuple[object, ...]", attributes)]


def _attribute(attribute: object) -> str:
    if isinstance(attribute, str):
        return attribute
    qualname = getattr(attribute, "__qualname__", None)
    if isinstance(qualname, str):
        return f"{getattr(attribute, '__module__', '')}.{qualname}"
    return repr(attribute)


def _vote(vote: object) -> str:
    return vote.name.lower() if isinstance(vote, Access) else str(vote)


def _class_of(service: object) -> str | None:
    return _qualified(type(service)) if service is not None else None


def _qualified(klass: type) -> str:
    return f"{klass.__module__}.{klass.__qualname__}"
