"""Which class a deployment's registered clients are."""

from __future__ import annotations

from dataclasses import dataclass, field

from xtr_security_oauth2_server.exception.invalid_configuration_error import (
    InvalidConfigurationError,
)
from xtr_security_oauth2_server.model.abstract_client import AbstractClient
from xtr_security_oauth2_server.model.client import Client

__all__ = ["ClientConfig"]


@dataclass(frozen=True, slots=True)
class ClientConfig:
    """The client class this deployment registers its clients as.

    The shipped :class:`~xtr_security_oauth2_server.model.client.Client` is
    enough for a deployment that needs nothing of its own. One that needs
    columns beside the registration — an owning organisation, a contact — names
    its own class here, maps it itself, and the token tables point at its table
    instead.

    Attributes:
        classname: The class registered clients are, which must carry
            :class:`~xtr_security_oauth2_server.model.abstract_client.AbstractClient`'s
            registration.
    """

    classname: type[AbstractClient] = field(default=Client)

    def __post_init__(self) -> None:
        """Refuse a class that is not a client.

        Raises:
            InvalidConfigurationError: When ``classname`` does not derive from
                ``AbstractClient``. Everything that reads a client — the
                repository bridge, the mapping, the commands — reads the
                registration that base declares, so a class without it would
                fail one call at a time instead of here.
        """
        _refuse_unless_a_client(self.classname)


def _refuse_unless_a_client(configured: object) -> None:
    """Refuse ``configured`` unless it is a class carrying a client's registration.

    Takes a plain object on purpose: the field's annotation says what a client
    class is, but a configuration is written in an application that may never
    be type-checked, so the guard has to be a real one.

    Raises:
        InvalidConfigurationError: When ``configured`` is not a subclass of
            ``AbstractClient``.
    """
    if not isinstance(configured, type) or not issubclass(configured, AbstractClient):
        raise InvalidConfigurationError(
            f"The setting client.classname is {configured!r}, which is not a subclass "
            f"of {AbstractClient.__module__}.{AbstractClient.__qualname__}; a client class "
            "carries that base's registration.",
        )
