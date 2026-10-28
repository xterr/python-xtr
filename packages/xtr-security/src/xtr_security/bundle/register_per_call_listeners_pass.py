"""Gives the dispatchers the listeners that must be built per call.

The listeners a dispatcher keeps are singletons, but these hold what belongs
to one request — the forgery-token manager over the request's session, the
session strategy over its clearable storage — so they cannot be services the
dispatcher keeps. This pass places their per-call references into the
dispatcher's compiled listener map instead, after the event dispatcher bundle
has worked the map out and the security bundle has merged the shared
listeners into it, so the positions they land in are the positions they run
in. Two of them belong on the main dispatcher, over the kernel's own events:
the context step's response half, which stores the token a stateful request
authenticated back into its session, and the naming of the matched firewall
on the logout-address generator.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast, final

from xtr_event_dispatcher import EventDispatcherInterface
from xtr_event_dispatcher.bundle import ListenerMap
from xtr_event_dispatcher_contracts import event_name_of
from xtr_http_kernel import RequestEvent, ResponseEvent
from xtr_security_http import (
    CheckPassportEvent,
    LoginSuccessEvent,
    LogoutEvent,
)
from xtr_security_http.event_listener.csrf_protection_listener import (
    PRIORITY as CSRF_PROTECTION_PRIORITY,
)

from xtr_security.bundle._csrf_listeners import (
    PerCallListener,
    check_the_passport_token,
    clear_csrf_tokens_on_logout,
    session_strategy_listener,
)
from xtr_security.bundle._csrf_wiring import form_login_asks_for_csrf
from xtr_security.bundle._logout_wiring import logout_context_key, name_the_current_firewall
from xtr_security.bundle._stateful_wiring import (
    context_listener_name,
    session_authentication_strategy_name,
    store_the_context,
)
from xtr_security.bundle.firewall_dispatcher_name import firewall_dispatcher_name
from xtr_security.bundle.security_config import SecurityConfig

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_dependency_injection import ContainerBuilder
    from xtr_event_dispatcher.bundle._listener_reference import (
        ListenerReference,
    )

    from xtr_security.firewall_config import FirewallConfig

__all__ = ["RegisterPerCallListenersPass"]

_DEFAULT_PRIORITY: Final = 0
"""Where the landed clearing and strategy listeners run: the default priority."""

_CURRENT_FIREWALL_PRIORITY: Final = 4
"""Where the matched firewall is named on the generator: after the firewall.

The firewall runs at its own priority of 8, parking the context this listener
names; anything later would do as well, but a priority of its own keeps the
constraint readable where it is declared.
"""


@final
class RegisterPerCallListenersPass:
    """Places the per-call listeners into the dispatchers' maps.

    The forgery check runs at the priority the landed listener declares,
    ahead of every other listener of that priority — a forged request is
    refused before any user is loaded, and the resolve step's dummy burn has
    no user timing to equalise. The token clearing and the session strategy
    run at the default priority their landed listeners declare, behind the
    listeners already placed there. The main dispatcher's two — the token
    write-back at the default priority, the firewall naming after the
    firewall — land behind the listeners already placed at theirs.
    """

    __slots__ = ()

    def process(self, builder: ContainerBuilder) -> None:
        """Insert the per-call listeners into the dispatchers' maps."""
        config = builder.get_extension_config(SecurityConfig)
        for name, firewall in config.firewalls.items():
            dispatcher = firewall_dispatcher_name(name)
            if not builder.has_definition(EventDispatcherInterface, dispatcher):
                continue
            definition = builder.get_definition(EventDispatcherInterface, dispatcher)
            listeners = cast("ListenerMap", definition.get_arguments()["listeners"])
            inserted = _insertions_of(name, firewall)
            if inserted:
                _ = definition.set_argument("listeners", _with_inserted(listeners, inserted))
        main_inserted = _main_insertions_of(config)
        if main_inserted:
            definition = builder.get_definition(EventDispatcherInterface, None)
            listeners = cast("ListenerMap", definition.get_arguments()["listeners"])
            _ = definition.set_argument("listeners", _with_inserted(listeners, main_inserted))


def _insertions_of(
    name: str,
    firewall: FirewallConfig,
) -> dict[str, list[tuple[int, object, bool]]]:
    """Return the listeners the firewall's configuration asks to run per call.

    Each entry is the priority it runs at, its per-call reference, and
    whether it runs ahead of the listeners its dispatcher already has at
    that priority — the forgery check ahead, so nothing loads a user before
    a forged request is refused; the clearing and the strategy behind.
    """
    inserted: dict[str, list[tuple[int, object, bool]]] = {}
    if form_login_asks_for_csrf(firewall):
        inserted.setdefault(event_name_of(CheckPassportEvent), []).append(
            (CSRF_PROTECTION_PRIORITY, PerCallListener(check_the_passport_token), True),
        )
    if firewall.logout is not None and firewall.logout.clear_csrf_tokens:
        inserted.setdefault(event_name_of(LogoutEvent), []).append(
            (_DEFAULT_PRIORITY, PerCallListener(clear_csrf_tokens_on_logout), False),
        )
    if firewall.security and not firewall.stateless:
        inserted.setdefault(event_name_of(LoginSuccessEvent), []).append(
            (
                _DEFAULT_PRIORITY,
                PerCallListener(
                    session_strategy_listener(session_authentication_strategy_name(name))
                ),
                False,
            ),
        )
    return inserted


def _main_insertions_of(
    config: SecurityConfig,
) -> dict[str, list[tuple[int, object, bool]]]:
    """Return the per-call listeners the main dispatcher runs.

    Each stateful firewall's context step gains its response half — the
    write-back storing the token the request authenticated into the session
    it reattached — and the logout-address generator gains the naming of
    the matched firewall, for the firewalls that registered a logout. Both
    resolve their service from the request's own unit of work, the way the
    firewall dispatchers' per-call listeners do.
    """
    inserted: dict[str, list[tuple[int, object, bool]]] = {}
    write_backs: list[tuple[int, object, bool]] = [
        (
            _DEFAULT_PRIORITY,
            PerCallListener(store_the_context(context_listener_name(name))),
            False,
        )
        for name, firewall in config.firewalls.items()
        if firewall.security and not firewall.stateless
    ]
    if write_backs:
        inserted[event_name_of(ResponseEvent)] = write_backs
    contexts = {
        name: logout_context_key(name, firewall)
        for name, firewall in config.firewalls.items()
        if firewall.logout is not None
    }
    if contexts:
        inserted.setdefault(event_name_of(RequestEvent), []).append(
            (
                _CURRENT_FIREWALL_PRIORITY,
                PerCallListener(name_the_current_firewall(contexts)),
                False,
            ),
        )
    return inserted


def _with_inserted(
    listeners: ListenerMap,
    inserted: Mapping[str, Sequence[tuple[int, object, bool]]],
) -> ListenerMap:
    """Return a copy of ``listeners`` carrying every insertion at its place."""
    by_event = dict(listeners.by_event)
    for event_name, insertions in inserted.items():
        entries: list[tuple[int, object]] = list(by_event.get(event_name, ()))
        for priority, reference, ahead in insertions:
            entries = (
                _placed_ahead(entries, priority, reference)
                if ahead
                else _placed_behind(entries, priority, reference)
            )
        by_event[event_name] = cast("tuple[tuple[int, ListenerReference], ...]", tuple(entries))
    return ListenerMap(by_event)


def _placed_ahead(
    entries: Sequence[tuple[int, object]],
    priority: int,
    reference: object,
) -> list[tuple[int, object]]:
    """Place ``reference`` ahead of the first entry running at ``priority`` or later."""
    placed: list[tuple[int, object]] = []
    for index, entry in enumerate(entries):
        if entry[0] <= priority:
            placed.append((priority, reference))
            placed.extend(entries[index:])
            return placed
        placed.append(entry)
    placed.append((priority, reference))
    return placed


def _placed_behind(
    entries: Sequence[tuple[int, object]],
    priority: int,
    reference: object,
) -> list[tuple[int, object]]:
    """Place ``reference`` behind the last entry running above ``priority``."""
    placed: list[tuple[int, object]] = []
    for index, entry in enumerate(entries):
        if entry[0] < priority:
            placed.append((priority, reference))
            placed.extend(entries[index:])
            return placed
        placed.append(entry)
    placed.append((priority, reference))
    return placed
