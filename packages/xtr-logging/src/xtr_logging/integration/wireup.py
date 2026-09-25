"""A logger per channel from a wireup container.

Install with the ``wireup`` extra. A service asks for the default channel's
logger by its interface, and for any other channel by qualifying it with the
channel's name::

    from typing import Annotated

    from wireup import Inject, injectable

    from xtr_logging import LoggerInterface


    @injectable
    class Checkout:
        def __init__(
            self,
            logger: LoggerInterface,
            audit: Annotated[LoggerInterface, Inject(qualifier="security")],
        ) -> None: ...

One call where the container is built::

    from xtr_logging.integration import wireup as logging

    container = wireup.create_async_container(
        injectables=[app.services, *logging.injectables(CONFIG)],
    )

The container can also hand out the
:class:`~xtr_logging.logger_factory.LoggerFactory` itself, to close it on
shutdown or reset it between messages.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import wireup
from xtr_logging_contracts import LoggerInterface

from xtr_logging.logger_factory import LoggerFactory

if TYPE_CHECKING:
    from xtr_logging.config.logging_config import LoggingConfig
    from xtr_logging.config.services import Services
    from xtr_logging.processor.processor_registry import ProcessorRegistry

__all__ = ["injectables"]


def injectables(
    source: LoggingConfig | LoggerFactory,
    *,
    services: Services | None = None,
    registry: ProcessorRegistry | None = None,
) -> list[object]:
    """Return what to spread into ``create_async_container(injectables=[...])``.

    The container then provides the ``LoggerFactory``, a ``LoggerInterface``
    for the default channel, and a ``LoggerInterface`` qualified by each
    channel's name — the default channel included.

    Args:
        source: A configuration to build a factory from, or a factory already
            built — pass one to keep a reference for closing it yourself.
        services: Objects the configuration names by id; only used with a
            configuration.
        registry: Where declared processors are read from; only used with a
            configuration.

    Returns:
        Injectables for ``create_async_container`` or ``create_sync_container``.
    """
    factory = (
        source
        if isinstance(source, LoggerFactory)
        else LoggerFactory(source, services=services, registry=registry)
    )
    provided: list[object] = [
        wireup.instance(factory, as_type=LoggerFactory),
        wireup.instance(factory.logger(), as_type=LoggerInterface),
    ]
    provided.extend(
        wireup.instance(factory.logger(channel), as_type=LoggerInterface, qualifier=channel)
        for channel in factory.channels
    )
    return provided
