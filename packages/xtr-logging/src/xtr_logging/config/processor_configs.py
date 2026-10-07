"""Processors as configuration.

A processor applies to every channel by default; ``channel`` limits it to
one, ``handler`` attaches it to one handler instead. Never both: handlers are
shared between channels, so "this handler, on that channel" has no meaning.
"""

from __future__ import annotations

import re
from typing import TypeAlias

import msgspec
from typing_extensions import override
from xtr_logging_contracts import Level

from xtr_logging.exception.invalid_option_error import InvalidOptionError
from xtr_logging.processor._target import refuse_both_targets
from xtr_logging.processor.redacting_processor import DEFAULT_KEY_PATTERN, DEFAULT_MASK

__all__ = [
    "ContextVarsProcessorConfig",
    "HostnameProcessorConfig",
    "IntrospectionProcessorConfig",
    "PlaceholderProcessorConfig",
    "ProcessIdProcessorConfig",
    "ProcessorConfig",
    "RedactingProcessorConfig",
    "ServiceProcessorConfig",
    "TagProcessorConfig",
    "UidProcessorConfig",
]


class _ProcessorConfigBase(
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
        refuse_both_targets(self.channel, self.handler)


class PlaceholderProcessorConfig(
    _ProcessorConfigBase, frozen=True, kw_only=True, tag="placeholder"
):
    """A :class:`~xtr_logging.processor.placeholder_processor.PlaceholderProcessor`."""

    date_format: str | None = None
    remove_used_context_fields: bool = False


class UidProcessorConfig(_ProcessorConfigBase, frozen=True, kw_only=True, tag="uid"):
    """A :class:`~xtr_logging.processor.uid_processor.UidProcessor`."""

    length: int = 7


class HostnameProcessorConfig(_ProcessorConfigBase, frozen=True, kw_only=True, tag="hostname"):
    """A :class:`~xtr_logging.processor.hostname_processor.HostnameProcessor`."""


class ProcessIdProcessorConfig(_ProcessorConfigBase, frozen=True, kw_only=True, tag="process_id"):
    """A :class:`~xtr_logging.processor.process_id_processor.ProcessIdProcessor`."""


class IntrospectionProcessorConfig(
    _ProcessorConfigBase, frozen=True, kw_only=True, tag="introspection"
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


class TagProcessorConfig(_ProcessorConfigBase, frozen=True, kw_only=True, tag="tags"):
    """A :class:`~xtr_logging.processor.tag_processor.TagProcessor`."""

    tags: tuple[str, ...] = ()


class RedactingProcessorConfig(_ProcessorConfigBase, frozen=True, kw_only=True, tag="redacting"):
    """A :class:`~xtr_logging.processor.redacting_processor.RedactingProcessor`."""

    keys: str | None = DEFAULT_KEY_PATTERN
    values: tuple[str, ...] = ()
    mask: str = DEFAULT_MASK

    @override
    def __post_init__(self) -> None:
        """Check the targets, and that every pattern compiles.

        Raises:
            InvalidOptionError: If a pattern is not a valid regular expression.
        """
        super().__post_init__()
        if self.keys:
            _compile("keys", self.keys)
        for pattern in self.values:
            _compile("values", pattern)


class ContextVarsProcessorConfig(
    _ProcessorConfigBase, frozen=True, kw_only=True, tag="context_vars"
):
    """A :class:`~xtr_logging.processor.context_vars_processor.ContextVarsProcessor`."""

    key: str | None = None


class ServiceProcessorConfig(_ProcessorConfigBase, frozen=True, kw_only=True, tag="service"):
    """A processor supplied to the factory under ``id``."""

    id: str


ProcessorConfig: TypeAlias = (
    PlaceholderProcessorConfig
    | UidProcessorConfig
    | HostnameProcessorConfig
    | ProcessIdProcessorConfig
    | IntrospectionProcessorConfig
    | TagProcessorConfig
    | RedactingProcessorConfig
    | ContextVarsProcessorConfig
    | ServiceProcessorConfig
)
"""Any processor entry, told apart by its ``type``."""


def _compile(option: str, pattern: str) -> None:
    try:
        _ = re.compile(pattern)
    except re.error as error:
        raise InvalidOptionError(
            option, pattern, f"is not a regular expression: {error}"
        ) from error
