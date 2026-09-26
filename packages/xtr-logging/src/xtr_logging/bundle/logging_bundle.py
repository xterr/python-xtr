"""The xtr-logging bundle: one logger per channel, from a container.

A container is asked for :class:`~xtr_logging_contracts.LoggerInterface` and
receives the default channel's logger; a qualified request
(``Target("security")``) returns the logger for that channel. The
:class:`~xtr_logging.logger_factory.LoggerFactory` is registered too, so
tests can reach any handler and the resetter can reset it between messages.

Requires the clock bundle only when it is present: the boot-time clock a
:class:`~xtr_logging.logger_factory.LoggerFactory` reads is looked up when
``kernel.bundles`` contains ``"clock"``, and left ambient otherwise, so a
missing clock bundle costs nothing at build time.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Iterable, Iterator
from typing import TYPE_CHECKING, cast, final

from typing_extensions import override
from xtr_clock import ClockInterface
from xtr_dependency_injection import (
    Bundle,
    ContainerBuilder,
    ServiceConfigurator,
    as_bundle,
    bundle_active,
    required_bundle,
)
from xtr_logging_contracts import LoggerInterface
from xtr_service_contracts import ContainerInterface

from xtr_logging.config.handler_specs import (
    ConsoleHandlerSpec,
    FormattedHandlerSpec,
    ServiceHandlerSpec,
)
from xtr_logging.config.logging_config import LoggingConfig
from xtr_logging.config.processor_specs import ServiceProcessorSpec
from xtr_logging.config.services import Services
from xtr_logging.config.wrapper_handler_specs import FingersCrossedHandlerSpec
from xtr_logging.exception.unknown_service_error import UnknownServiceError
from xtr_logging.formatter.formatter_interface import FormatterInterface
from xtr_logging.handler.fingers_crossed.activation_strategy_interface import (
    ActivationStrategyInterface,
)
from xtr_logging.handler.handler_interface import HandlerInterface
from xtr_logging.logger_factory import LoggerFactory
from xtr_logging.processor.processor_interface import ProcessorInterface
from xtr_logging.processor.processor_registry import (
    ProcessorRegistry,
    processors_declared_on,
)

if TYPE_CHECKING:
    from xtr_logging.processor.processor_registry import ProcessorDeclaration

__all__ = ["LoggingBundle"]


@final
@required_bundle("xtr_clock.bundle:ClockBundle", ignore_on_invalid=True)
@as_bundle("logging", config=LoggingConfig)
class LoggingBundle(Bundle[LoggingConfig]):
    """Turns a :class:`LoggingConfig` into a logger per channel in the container."""

    def __init__(self) -> None:
        """Start empty; per-kernel state is populated during ``build``/``load_extension``."""
        self._registry: ProcessorRegistry = ProcessorRegistry()
        self._declared_classes: list[type[ProcessorInterface]] = []

    @override
    def build(self, builder: ContainerBuilder) -> None:
        """Register attribute autoconfiguration for ``@as_processor`` classes."""

        def register_processor(
            obj: object, meta: ProcessorDeclaration, services: ServiceConfigurator
        ) -> None:
            if not isinstance(obj, type):
                return
            processor_cls = cast("type[ProcessorInterface]", obj)
            _ = services.set(processor_cls)
            self._declared_classes.append(processor_cls)
            self._registry.register_class(
                processor_cls,
                channel=meta.channel,
                handler=meta.handler,
                priority=meta.priority,
            )

        builder.register_attribute_for_autoconfiguration(
            processors_declared_on,
            register_processor,
        )

    @override
    def load_extension(
        self,
        config: LoggingConfig,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        """Register the :class:`LoggerFactory`, a :class:`Services`, and every logger."""
        has_clock = bundle_active(builder, "clock")
        registry = self._registry
        declared_classes = self._declared_classes

        # The factories inject the config rather than closing over ``config``:
        # the container hands them a copy with every environment placeholder
        # resolved, which the value loaded here is not.
        async def services_factory(
            container: ContainerInterface, resolved: LoggingConfig
        ) -> Services:
            for cls in declared_classes:
                registry.bind_class(cls, await container.get(cls))
            return await _resolve_services(resolved, container)

        _ = services.set(services_factory)

        if has_clock:

            async def logger_factory_with_clock(
                resolved: LoggingConfig, services_from_config: Services, clock: ClockInterface
            ) -> AsyncIterator[LoggerFactory]:
                factory = LoggerFactory(
                    resolved, services=services_from_config, registry=registry, clock=clock
                )
                try:
                    yield factory
                finally:
                    factory.close()

            _ = services.set(logger_factory_with_clock)
        else:

            async def logger_factory_no_clock(
                resolved: LoggingConfig, services_from_config: Services
            ) -> AsyncIterator[LoggerFactory]:
                factory = LoggerFactory(resolved, services=services_from_config, registry=registry)
                try:
                    yield factory
                finally:
                    factory.close()

            _ = services.set(logger_factory_no_clock)

        def default_logger(factory: LoggerFactory) -> LoggerInterface:
            return factory.logger()

        _ = services.set(default_logger)

        for channel in config.all_channels:
            _ = services.set(_channel_logger_factory(channel), qualifier=channel)

    @override
    def process(self, builder: ContainerBuilder) -> None:
        """Check every service id the configuration names exists in the container."""
        config = builder.get_extension_config(LoggingConfig)
        for kind, service_type, ids in _service_ids_by_kind(config):
            for service_id in ids:
                if not builder.has(service_type, service_id):
                    raise UnknownServiceError(kind, service_id, ())


def _channel_logger_factory(channel: str) -> Callable[[LoggerFactory], LoggerInterface]:
    """Build a factory function that returns the logger for ``channel``.

    Defined outside :meth:`LoggingBundle.load_extension` so each channel gets
    its own function object — the engine keys factories by identity, and one
    closure per channel keeps the emission and error messages readable.
    """

    def channel_logger(factory: LoggerFactory) -> LoggerInterface:
        return factory.logger(channel)

    channel_logger.__name__ = f"channel_logger_{channel}"
    channel_logger.__qualname__ = channel_logger.__name__
    return channel_logger


async def _resolve_services(config: LoggingConfig, container: ContainerInterface) -> Services:
    """Build a :class:`Services` from ``config``'s ids, resolved through ``container``."""
    handlers: dict[str, HandlerInterface] = {}
    formatters: dict[str, FormatterInterface] = {}
    processors: dict[str, ProcessorInterface] = {}
    strategies: dict[str, ActivationStrategyInterface] = {}
    for kind, _service_type, ids in _service_ids_by_kind(config):
        for service_id in ids:
            if kind == "handler":
                handlers[service_id] = await container.get(HandlerInterface, service_id)
            elif kind == "formatter":
                formatters[service_id] = await container.get(FormatterInterface, service_id)
            elif kind == "processor":
                processors[service_id] = await container.get(ProcessorInterface, service_id)
            else:
                strategies[service_id] = await container.get(
                    ActivationStrategyInterface, service_id
                )
    return Services(
        handlers=handlers,
        formatters=formatters,
        processors=processors,
        activation_strategies=strategies,
    )


def _service_ids_by_kind(
    config: LoggingConfig,
) -> Iterator[tuple[str, type, tuple[str, ...]]]:
    """Yield ``(kind, service_type, ids)`` for each family of service the config names."""
    yield ("handler", HandlerInterface, tuple(_handler_ids(config)))
    yield ("formatter", FormatterInterface, tuple(_formatter_ids(config)))
    yield ("processor", ProcessorInterface, tuple(_processor_ids(config)))
    yield ("activation_strategy", ActivationStrategyInterface, tuple(_strategy_ids(config)))


def _handler_ids(config: LoggingConfig) -> Iterable[str]:
    for spec in config.handlers.values():
        if isinstance(spec, ServiceHandlerSpec):
            yield spec.id


def _formatter_ids(config: LoggingConfig) -> Iterable[str]:
    seen: set[str] = set()
    for spec in config.handlers.values():
        formatter: object = None
        if isinstance(spec, (FormattedHandlerSpec, ConsoleHandlerSpec)):
            formatter = spec.formatter
        if isinstance(formatter, str) and formatter not in seen:
            seen.add(formatter)
            yield formatter


def _processor_ids(config: LoggingConfig) -> Iterable[str]:
    for spec in config.processors:
        if isinstance(spec, ServiceProcessorSpec):
            yield spec.id


def _strategy_ids(config: LoggingConfig) -> Iterable[str]:
    for spec in config.handlers.values():
        if isinstance(spec, FingersCrossedHandlerSpec) and spec.activation_strategy is not None:
            yield spec.activation_strategy
