"""Small fakes the unit tests build their doubles from."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar, cast, final

from typing_extensions import override
from xtr_dependency_injection import ServiceLocator
from xtr_event_dispatcher_contracts import EventDispatcherInterface
from xtr_security_core.user.attributes_based_user_provider_interface import (
    AttributesBasedUserProviderInterface,
)
from xtr_security_core.user.in_memory_user import InMemoryUser
from xtr_security_core.user.user_interface import UserInterface
from xtr_security_core.user.user_provider_interface import UserProviderInterface

if TYPE_CHECKING:
    from collections.abc import Hashable, Mapping, Sequence

    from xtr_event_dispatcher_contracts import Event
    from xtr_service_contracts import ContainerInterface

__all__ = [
    "AttributedUser",
    "AttributesRecordingProvider",
    "PlainUserProvider",
    "RecordingDispatcher",
    "RejectingDispatcher",
    "provider_locator",
]

_EventT = TypeVar("_EventT")


@final
class RecordingDispatcher(EventDispatcherInterface):
    """An event dispatcher that records every event it is handed, in order."""

    def __init__(self) -> None:
        """Start with no recorded events."""
        self.events: list[Event] = []

    @override
    async def dispatch(self, event: _EventT, event_name: str | type | None = None) -> _EventT:
        """Record the event and return it, running no listener."""
        del event_name
        self.events.append(cast("Event", event))
        return event

    def types(self) -> list[type]:
        """Return the classes of the events recorded, in order."""
        return [type(one) for one in self.events]


@final
class RejectingDispatcher(EventDispatcherInterface):
    """A dispatcher that rejects one kind of event by marking it invalid."""

    def __init__(self, reject: type) -> None:
        """Reject every event that is an instance of ``reject``."""
        self._reject = reject

    @override
    async def dispatch(self, event: _EventT, event_name: str | type | None = None) -> _EventT:
        """Mark the target event invalid, leaving every other event untouched."""
        del event_name
        if isinstance(event, self._reject):
            marker = getattr(event, "mark_as_invalid", None)
            if callable(marker):
                _ = marker()
        return event


@final
class AttributedUser(UserInterface):
    """A user that also answers to a fixed extra claim attribute."""

    def __init__(self, identifier: str, email: str) -> None:
        """Record the user's ``identifier`` and its extra ``email`` claim."""
        self._identifier = identifier
        self.email = email

    @override
    def get_user_identifier(self) -> str:
        """Return the identifier."""
        return self._identifier

    @override
    def get_roles(self) -> Sequence[str]:
        """Report the default role."""
        return ("ROLE_USER",)


@final
class PlainUserProvider(UserProviderInterface):
    """A plain provider that returns a fixed user, ignoring any attributes."""

    def __init__(self, user: UserInterface) -> None:
        """Return ``user`` for the identifier it is named by."""
        self._user: UserInterface = user
        self.calls: list[str] = []

    @override
    async def load_user_by_identifier(self, identifier: str) -> UserInterface:
        """Return the fixed user, recording the identifier asked for."""
        self.calls.append(identifier)
        return self._user

    @override
    def supports_class(self, user_class: type) -> bool:
        """Support the in-memory user class."""
        return issubclass(user_class, InMemoryUser)


@final
class _ProviderContainer:
    """A container over a fixed mapping of user providers, for a service locator."""

    def __init__(self, providers: Mapping[str, UserProviderInterface]) -> None:
        """Answer ``get`` from ``providers`` keyed by qualifier."""
        self._providers = dict(providers)

    async def get(self, service: type[object], qualifier: Hashable | None = None) -> object:
        """Return the provider registered under ``qualifier``."""
        del service
        return self._providers[cast("str", qualifier)]

    def has(self, service: type[object], qualifier: Hashable | None = None) -> bool:
        """Tell whether a provider is registered under ``qualifier``."""
        del service
        return qualifier in self._providers

    def get_parameter(self, name: str) -> object:  # pragma: no cover - unused
        """Unused by the locator; present for the container contract."""
        raise KeyError(name)

    def has_parameter(self, name: str) -> bool:  # pragma: no cover - unused
        """Unused by the locator; present for the container contract."""
        del name
        return False


def provider_locator(
    providers: Mapping[str, UserProviderInterface],
) -> ServiceLocator[UserProviderInterface]:
    """Build a real service locator over a fixed mapping of user providers."""
    container = cast("ContainerInterface", cast("object", _ProviderContainer(providers)))
    entries: Mapping[Hashable, tuple[type, str | None]] = {
        name: (UserProviderInterface, name) for name in providers
    }
    return ServiceLocator(container, entries)


@final
class AttributesRecordingProvider(AttributesBasedUserProviderInterface):
    """An attributes-based provider that records the payload it was handed."""

    def __init__(self, user: UserInterface) -> None:
        """Return ``user``, recording the attributes each call carries."""
        self._user: UserInterface = user
        self.attributes: list[Mapping[str, object] | None] = []

    @override
    async def load_user_by_identifier(
        self,
        identifier: str,
        attributes: Mapping[str, object] | None = None,
    ) -> UserInterface:
        """Return the fixed user, recording the attributes handed in."""
        del identifier
        self.attributes.append(attributes)
        return self._user

    @override
    def supports_class(self, user_class: type) -> bool:
        """Support the in-memory user class."""
        return issubclass(user_class, InMemoryUser)
