"""Objects the configuration refers to by id — ``type: service`` and friends."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_logging.formatter.formatter_interface import FormatterInterface
    from xtr_logging.handler.fingers_crossed.activation_strategy_interface import (
        ActivationStrategyInterface,
    )
    from xtr_logging.handler.handler_interface import HandlerInterface
    from xtr_logging.processor.processor_interface import ProcessorInterface

__all__ = ["Services"]


def _no_handlers() -> Mapping[str, HandlerInterface]:
    return {}


def _no_formatters() -> Mapping[str, FormatterInterface]:
    return {}


def _no_processors() -> Mapping[str, ProcessorInterface]:
    return {}


def _no_strategies() -> Mapping[str, ActivationStrategyInterface]:
    return {}


@dataclass(frozen=True, slots=True)
class Services:
    """Objects a configuration can name but not describe.

    Configuration is data, and some things are objects — a handler for a
    service this library does not ship, a formatter of your own. Hand them
    over here under an id, and name that id in the configuration::

        LoggerFactory(
            LoggingConfig(handlers={"sentry": ServiceHandlerSpec(id="sentry")}),
            services=Services(handlers={"sentry": SentryHandler(dsn)}),
        )

    Attributes:
        handlers: For ``type: service`` handlers.
        formatters: For a handler's ``formatter`` given as a string.
        processors: For ``type: service`` processors.
        activation_strategies: For a fingers-crossed handler's
            ``activation_strategy``.
    """

    handlers: Mapping[str, HandlerInterface] = field(default_factory=_no_handlers)
    formatters: Mapping[str, FormatterInterface] = field(default_factory=_no_formatters)
    processors: Mapping[str, ProcessorInterface] = field(default_factory=_no_processors)
    activation_strategies: Mapping[str, ActivationStrategyInterface] = field(
        default_factory=_no_strategies,
    )
