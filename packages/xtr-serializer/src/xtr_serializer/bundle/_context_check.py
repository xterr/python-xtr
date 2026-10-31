"""The check a configured default context goes through."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from xtr_serializer.exception import InvalidArgumentError

__all__ = ["check_context"]


def check_context(context: object, described: str) -> None:
    """Refuse ``context`` unless it is a mapping keyed by strings.

    A call's context is keyed by strings, and a configured one is merged into it key by key, so
    a key of another kind would only ever be a typo that nothing reads. ``described`` says which
    context it is, for the message. ``context`` is taken as anything: a configuration is written
    by hand, and its annotations are not enforced.

    Raises:
        InvalidArgumentError: When ``context`` is not a mapping, or a key is not a string.
    """
    if not isinstance(context, Mapping):
        raise InvalidArgumentError(f"{described} must be a mapping keyed by strings")
    for key in cast("Mapping[object, object]", context):
        if not isinstance(key, str):
            raise InvalidArgumentError(
                f"{described} is keyed by strings, but one key is of type {type(key).__name__}"
            )
