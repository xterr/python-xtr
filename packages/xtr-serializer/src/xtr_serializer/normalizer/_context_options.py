"""A call's context read as the options pydantic writes and reads with, each checked."""

from __future__ import annotations

from collections.abc import Set as AbstractSet
from typing import TYPE_CHECKING, Literal, NamedTuple, cast

from xtr_serializer.exception import InvalidArgumentError

from .denormalizer_interface import COLLECT_DENORMALIZATION_ERRORS
from .pydantic_normalizer_keys import (
    ALLOW_EXTRA_ATTRIBUTES,
    ATTRIBUTES,
    BY_ALIAS,
    FROM_ATTRIBUTES,
    IGNORED_ATTRIBUTES,
    POPULATE_BY_NAME,
    SKIP_DEFAULT_VALUES,
    SKIP_NULL_VALUES,
    SKIP_UNSET_VALUES,
    STRICT,
)

if TYPE_CHECKING:
    from xtr_serializer.context.context import Context

__all__ = ["ReadOptions", "WriteOptions", "read_options", "write_options"]


class WriteOptions(NamedTuple):
    """What to write, as pydantic's dump takes it."""

    include: set[str] | None
    exclude: set[str] | None
    by_alias: bool
    exclude_none: bool
    exclude_unset: bool
    exclude_defaults: bool

    @property
    def partial(self) -> bool:
        """Whether some attributes or values are left out, so the data is not meant to read back."""
        return (
            self.include is not None
            or self.exclude is not None
            or self.exclude_none
            or self.exclude_unset
            or self.exclude_defaults
        )


class ReadOptions(NamedTuple):
    """How to read, as pydantic's validation takes it, and whether to collect every error."""

    strict: bool | None
    extra: Literal["ignore", "forbid"] | None
    by_alias: bool
    by_name: bool | None
    from_attributes: bool
    collect: bool


def write_options(context: Context) -> WriteOptions:
    """Read the writing options of ``context``; aliases are on unless turned off."""
    return WriteOptions(
        include=_names(context, ATTRIBUTES),
        exclude=_names(context, IGNORED_ATTRIBUTES),
        by_alias=_flag(context, BY_ALIAS) is not False,
        exclude_none=_flag(context, SKIP_NULL_VALUES) is True,
        exclude_unset=_flag(context, SKIP_UNSET_VALUES) is True,
        exclude_defaults=_flag(context, SKIP_DEFAULT_VALUES) is True,
    )


def read_options(context: Context) -> ReadOptions:
    """Read the reading options of ``context``; an absent one leaves the type's own rule.

    Each is checked, in the order :class:`ReadOptions` lists them, ``STRICT`` first: a context
    holding several that are not a bool is refused naming the same one every time.
    """
    strict = _flag(context, STRICT)
    allow_extra = _flag(context, ALLOW_EXTRA_ATTRIBUTES)
    by_alias = _flag(context, BY_ALIAS) is not False
    by_name = _flag(context, POPULATE_BY_NAME)
    return ReadOptions(
        strict=strict,
        extra=None if allow_extra is None else "ignore" if allow_extra else "forbid",
        by_alias=by_alias,
        # pydantic needs one of alias and name to read by; without the alias, it is the name.
        by_name=by_name if by_alias else True,
        from_attributes=_flag(context, FROM_ATTRIBUTES) is True,
        collect=_flag(context, COLLECT_DENORMALIZATION_ERRORS) is True,
    )


def _flag(context: Context, key: str) -> bool | None:
    """Read an on/off option, ``None`` when it is absent, refusing anything but a bool."""
    value = context.get(key)
    if value is None or isinstance(value, bool):
        return value
    raise InvalidArgumentError(f"{key!r} must be a bool")


def _names(context: Context, key: str) -> set[str] | None:
    """Read a set of field names, ``None`` when it is absent, refusing anything else."""
    value = context.get(key)
    if isinstance(value, AbstractSet) and all(isinstance(name, str) for name in value):
        return cast("set[str]", set(value))
    if value is None:
        return None
    raise InvalidArgumentError(f"{key!r} must be a set of field names")
