"""Processors declared in code, waiting for a factory to attach them."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from .processor_declaration import ProcessorDeclaration
from .processor_descriptor import ProcessorDescriptor

if TYPE_CHECKING:
    from .processor_interface import ProcessorInterface

__all__ = ["ProcessorRegistry", "default_processor_registry"]


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
        """Declare ``descriptor`` — a ready-built processor instance.

        Declaring the same processor the same way again adds nothing, so a
        module decorating it twice does not run it twice.
        """
        entry = (descriptor.processor, descriptor.channel, descriptor.handler, descriptor.priority)
        if not any(_same(entry, known) for known in self._instance_entries):
            self._instance_entries.append(entry)

    def register_class(
        self,
        cls: type[ProcessorInterface],
        /,
        *,
        channel: str | None = None,
        handler: str | None = None,
        priority: int = 0,
    ) -> None:
        """Declare a processor class; it is instantiated lazily on first read.

        Declaring the same class the same way again adds nothing.
        """
        _ = ProcessorDeclaration(channel=channel, handler=handler, priority=priority)
        entry = (cls, channel, handler, priority)
        if not any(_same(entry, known) for known in self._class_entries):
            self._class_entries.append(entry)

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


def _same(entry: tuple[object, ...], known: tuple[object, ...]) -> bool:
    """Tell whether two declarations name the same processor, by identity, the same way."""
    return entry[0] is known[0] and entry[1:] == known[1:]


_DEFAULT = ProcessorRegistry()


def default_processor_registry() -> ProcessorRegistry:
    """Return the process-wide registry :func:`as_processor` declares into."""
    return _DEFAULT
