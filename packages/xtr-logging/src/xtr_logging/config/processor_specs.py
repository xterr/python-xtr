"""Processors as configuration.

A processor applies to every channel by default; ``channel`` limits it to
one, ``handler`` attaches it to one handler instead. Never both: handlers are
shared between channels, so "this handler, on that channel" has no meaning.
"""

from __future__ import annotations

from typing import TypeAlias

import msgspec
from typing_extensions import override
from xtr_logging_contracts import Level

from xtr_logging.exception.invalid_option_error import InvalidOptionError

__all__ = [
    "ContextVarsProcessorSpec",
    "HostnameProcessorSpec",
    "IntrospectionProcessorSpec",
    "PlaceholderProcessorSpec",
    "ProcessIdProcessorSpec",
    "ProcessorSpec",
    "ServiceProcessorSpec",
    "TagProcessorSpec",
    "UidProcessorSpec",
]


class _ProcessorSpecBase(
    msgspec.Struct,
    frozen=True,
    kw_only=True,
    forbid_unknown_fields=True,
    tag_field="type",
):
    channel: str | None = None
    handler: str | None = None
    priority: int = 0

    def __post_init__(self) -> None:
        if self.channel is not None and self.handler is not None:
            raise InvalidOptionError(
                "channel",
                self.channel,
                f"a processor targets a channel or a handler, not both (handler={self.handler})",
            )


class PlaceholderProcessorSpec(_ProcessorSpecBase, frozen=True, kw_only=True, tag="placeholder"):
    """A :class:`~xtr_logging.processor.placeholder_processor.PlaceholderProcessor`."""

    date_format: str | None = None
    remove_used_context_fields: bool = False


class UidProcessorSpec(_ProcessorSpecBase, frozen=True, kw_only=True, tag="uid"):
    """A :class:`~xtr_logging.processor.uid_processor.UidProcessor`."""

    length: int = 7


class HostnameProcessorSpec(_ProcessorSpecBase, frozen=True, kw_only=True, tag="hostname"):
    """A :class:`~xtr_logging.processor.hostname_processor.HostnameProcessor`."""


class ProcessIdProcessorSpec(_ProcessorSpecBase, frozen=True, kw_only=True, tag="process_id"):
    """A :class:`~xtr_logging.processor.process_id_processor.ProcessIdProcessor`."""


class IntrospectionProcessorSpec(
    _ProcessorSpecBase, frozen=True, kw_only=True, tag="introspection"
):
    """An :class:`~xtr_logging.processor.introspection_processor.IntrospectionProcessor`."""

    level: Level | str = Level.DEBUG
    skip_module_prefixes: tuple[str, ...] = ()
    skip_frames: int = 0

    @override
    def __post_init__(self) -> None:
        """Check the targets and the level."""
        super().__post_init__()
        _ = Level.parse(self.level)


class TagProcessorSpec(_ProcessorSpecBase, frozen=True, kw_only=True, tag="tags"):
    """A :class:`~xtr_logging.processor.tag_processor.TagProcessor`."""

    tags: tuple[str, ...] = ()


class ContextVarsProcessorSpec(_ProcessorSpecBase, frozen=True, kw_only=True, tag="context_vars"):
    """A :class:`~xtr_logging.processor.context_vars_processor.ContextVarsProcessor`."""

    key: str | None = None


class ServiceProcessorSpec(_ProcessorSpecBase, frozen=True, kw_only=True, tag="service"):
    """A processor supplied to the factory under ``id``."""

    id: str


ProcessorSpec: TypeAlias = (
    PlaceholderProcessorSpec
    | UidProcessorSpec
    | HostnameProcessorSpec
    | ProcessIdProcessorSpec
    | IntrospectionProcessorSpec
    | TagProcessorSpec
    | ContextVarsProcessorSpec
    | ServiceProcessorSpec
)
"""Any processor entry, told apart by its ``type``."""
