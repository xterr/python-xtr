"""Processors declared in code, waiting for a factory to attach them."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast, final

from xtr_logging.exception.invalid_option_error import InvalidOptionError

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .processor_interface import ProcessorInterface

__all__ = [
    "PROCESSORS_ATTRIBUTE",
    "ProcessorDeclaration",
    "ProcessorDescriptor",
    "ProcessorRegistry",
    "default_processor_registry",
    "processors_declared_on",
]

PROCESSORS_ATTRIBUTE = "__xtr_logging_processors__"
"""Where :func:`~xtr_logging.decorator.as_processor` records declarations on a class or function."""


@dataclass(frozen=True, slots=True)
class ProcessorDeclaration:
    """One declaration on a class or a function: what channel or handler, and priority."""

    channel: str | None = None
    handler: str | None = None
    priority: int = 0

    def __post_init__(self) -> None:
        """Refuse targeting both a channel and a handler."""
        if self.channel is not None and self.handler is not None:
            raise InvalidOptionError(
                "channel",
                self.channel,
                f"a processor targets a channel or a handler, not both (handler={self.handler})",
            )


def processors_declared_on(obj: object) -> Iterable[ProcessorDeclaration]:
    """Yield every :func:`~xtr_logging.decorator.as_processor` declaration on ``obj``.

    A reader for
    :meth:`~xtr_dependency_injection.builder.ContainerBuilder.register_attribute_for_autoconfiguration`:
    the logging bundle uses it so a class decorated with ``@as_processor``
    becomes a service, and a decorated function is attached as it is, to
    every logger the kernel builds.
    """
    declarations: object = getattr(obj, PROCESSORS_ATTRIBUTE, ())
    if not isinstance(declarations, tuple):
        return ()
    typed = cast("tuple[object, ...]", declarations)
    return tuple(entry for entry in typed if isinstance(entry, ProcessorDeclaration))


@dataclass(frozen=True, slots=True)
class ProcessorDescriptor:
    """One declared processor, and where it runs.

    Attributes:
        processor: The processor itself — always an instance when read from
            :attr:`ProcessorRegistry.descriptors`.
        channel: Run only on this channel's logger.
        handler: Run inside this handler instead of on a logger.
        priority: Higher runs first; ties keep declaration order.
    """

    processor: ProcessorInterface
    channel: str | None = None
    handler: str | None = None
    priority: int = 0

    def __post_init__(self) -> None:
        """Refuse targeting both a channel and a handler.

        Raises:
            InvalidOptionError: If both are given.
        """
        if self.channel is not None and self.handler is not None:
            raise InvalidOptionError(
                "channel",
                self.channel,
                f"a processor targets a channel or a handler, not both (handler={self.handler})",
            )


@final
class ProcessorRegistry:
    """Holds declared processors until a factory attaches them.

    :func:`~xtr_logging.decorator.as_processor` writes to the process-wide
    one by default, which is what lets a module declare a processor without
    importing the factory. Pass a registry of your own to keep two
    applications — or two tests — apart.

    Class declarations stay classes until :attr:`descriptors` is read for
    the first time, so importing a module that decorates a class costs no
    instantiation. A container-provided processor for a class is passed to
    :meth:`bind_class` before that first read, and the registry returns it
    instead of building one itself.
    """

    __slots__ = ("_bindings", "_class_entries", "_instance_entries", "_instances")

    def __init__(self) -> None:
        """Start empty."""
        self._instance_entries: list[tuple[ProcessorInterface, str | None, str | None, int]] = []
        self._class_entries: list[tuple[type[ProcessorInterface], str | None, str | None, int]] = []
        self._bindings: dict[type[ProcessorInterface], ProcessorInterface] = {}
        self._instances: dict[type[ProcessorInterface], ProcessorInterface] = {}

    @property
    def descriptors(self) -> tuple[ProcessorDescriptor, ...]:
        """Every declared processor, in declaration order.

        A class declaration is materialised on first read — from the binding
        set by :meth:`bind_class` if any, else by calling the class with no
        arguments — and cached for subsequent reads.
        """
        instance_descriptors = (
            ProcessorDescriptor(processor, channel, handler, priority)
            for processor, channel, handler, priority in self._instance_entries
        )
        class_descriptors = (
            ProcessorDescriptor(self._resolve(cls), channel, handler, priority)
            for cls, channel, handler, priority in self._class_entries
        )
        return (*instance_descriptors, *class_descriptors)

    def register(self, descriptor: ProcessorDescriptor) -> None:
        """Declare ``descriptor`` — a ready-built processor instance."""
        self._instance_entries.append(
            (descriptor.processor, descriptor.channel, descriptor.handler, descriptor.priority)
        )

    def register_class(
        self,
        cls: type[ProcessorInterface],
        /,
        *,
        channel: str | None = None,
        handler: str | None = None,
        priority: int = 0,
    ) -> None:
        """Declare a processor class; it is instantiated lazily on first read."""
        _ = ProcessorDeclaration(channel=channel, handler=handler, priority=priority)
        self._class_entries.append((cls, channel, handler, priority))

    def bind_class(self, cls: type[ProcessorInterface], instance: ProcessorInterface, /) -> None:
        """Provide ``instance`` for ``cls``, instead of instantiating it here."""
        self._bindings[cls] = instance

    def clear(self) -> None:
        """Forget every declared processor."""
        self._instance_entries.clear()
        self._class_entries.clear()
        self._bindings.clear()
        self._instances.clear()

    def _resolve(self, cls: type[ProcessorInterface]) -> ProcessorInterface:
        bound = self._bindings.get(cls)
        if bound is not None:
            return bound
        instance = self._instances.get(cls)
        if instance is None:
            instance = cls()
            self._instances[cls] = instance
        return instance


_DEFAULT = ProcessorRegistry()


def default_processor_registry() -> ProcessorRegistry:
    """Return the process-wide registry :func:`as_processor` declares into."""
    return _DEFAULT
