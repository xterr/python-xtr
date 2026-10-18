"""Ordering every firewall's listener chain, by priority and declared neighbours."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

from xtr_dependency_injection import sort_with_priorities
from xtr_dependency_injection.exception import ServiceOrderError, UnknownServiceError
from xtr_security_http.decorator.firewall_listener_order import firewall_listener_order_of
from xtr_security_http.firewall.firewall_listener_interface import FirewallListenerInterface

from xtr_security.exception import InvalidConfigurationError

from .firewall_context import FirewallContext
from .security_config import SecurityConfig

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from xtr_dependency_injection import ContainerBuilder

__all__ = ["SortFirewallListenersPass"]


@final
class SortFirewallListenersPass:
    """Puts each firewall's listener chain in the order it runs.

    A firewall's chain is its context definition's ``listeners``
    argument: the qualifiers of its listeners — each aliased under
    :class:`~xtr_security_http.firewall.firewall_listener_interface.FirewallListenerInterface`
    — in the order they were gathered. This pass sorts every chain by
    the priority its listeners declare, higher first, keeping the
    gathering order of listeners that share a priority; then it
    settles the ``@FirewallListenerOrder`` constraints a listener
    declares against its neighbours, which only reorder listeners that
    share a priority — a constraint that would need a listener to
    cross one fails the build, naming the firewall, so a listener
    cannot displace the chain's ordering by mistake.

    A firewall whose context carries no ``listeners`` argument is left
    untouched, so a configuration that gathers no chain builds exactly
    as before.

    The security bundle registers this after every bundle's ``process``
    hook, so a listener another bundle adds to a chain is ordered with
    the rest.
    """

    __slots__ = ()

    def process(self, builder: ContainerBuilder) -> None:
        """Sort every firewall's listener chain, in place.

        Raises:
            InvalidConfigurationError: When a chain names a qualifier no
                firewall listener is aliased under, when a listener declares
                no integer priority of its own, or when the declared
                constraints cannot be met within their priorities.
        """
        for name in builder.get_extension_config(SecurityConfig).firewalls:
            if not builder.has_definition(FirewallContext, name):
                continue
            definition = builder.get_definition(FirewallContext, name)
            arguments = definition.get_arguments()
            if "listeners" not in arguments:
                continue
            _ = definition.set_argument(
                "listeners", _ordered(builder, name, cast("Sequence[str]", arguments["listeners"]))
            )


def _ordered(
    builder: ContainerBuilder, firewall_name: str, qualifiers: Sequence[str]
) -> tuple[str, ...]:
    """Return ``qualifiers`` in the order their listeners run."""
    classes = {
        qualifier: _listener_class_of(builder, firewall_name, qualifier) for qualifier in qualifiers
    }
    priorities = {
        qualifier: _priority_of(listener_class) for qualifier, listener_class in classes.items()
    }
    constraints: dict[str, dict[str, list[str]]] = {}
    for qualifier, listener_class in classes.items():
        order = firewall_listener_order_of(listener_class)
        if order is not None and (order.before or order.after):
            constraints[qualifier] = {
                "before": [_named(target) for target in order.before],
                "after": [_named(target) for target in order.after],
            }
    aliases = {
        _named(listener_class): [
            qualifier
            for qualifier, named in classes.items()
            if _named(named) == _named(listener_class)
        ]
        for listener_class in classes.values()
    }
    try:
        resolved = sort_with_priorities(priorities, constraints, aliases)
    except ServiceOrderError as error:
        raise InvalidConfigurationError(
            f'Cannot order the listeners of the firewall "{firewall_name}": {error.reason}'
        ) from error
    return tuple(resolved)


def _listener_class_of(builder: ContainerBuilder, firewall_name: str, qualifier: str) -> type:
    """Return the listener class the chain's ``qualifier`` names.

    Raises:
        InvalidConfigurationError: When no firewall listener is aliased
            under the qualifier.
    """
    try:
        definition = builder.find_definition(FirewallListenerInterface, qualifier)
    except UnknownServiceError as error:
        raise InvalidConfigurationError(
            f'The listener chain of the firewall "{firewall_name}" names "{qualifier}", '
            "which no registered firewall listener is aliased under: register the listener "
            "and alias it under FirewallListenerInterface with that qualifier.",
        ) from error
    return definition.key[0]


def _priority_of(listener_class: type) -> int:
    """Return the priority the chain's listener declares, ``0`` when it declares none.

    Raises:
        InvalidConfigurationError: When the listener answers no integer
            priority — a class inheriting the interface's member without
            overriding it.
    """
    get_priority = cast(
        "Callable[[], object] | None", getattr(listener_class, "get_priority", None)
    )
    if get_priority is None:
        return 0
    priority = get_priority()
    if not isinstance(priority, int):
        raise InvalidConfigurationError(
            f"{listener_class.__qualname__} sits in a firewall's listener chain but answers "
            f"the priority {priority!r}: a listener declares get_priority() -> int.",
        )
    return priority


def _named(target: type | str) -> str:
    """Return the name a constraint addresses ``target`` by."""
    if isinstance(target, str):
        return target
    return f"{target.__module__}:{target.__qualname__}"
