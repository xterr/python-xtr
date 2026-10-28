"""The metadata of a declaration, its description included."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_workflow.exception import LogicError

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["build_metadata"]


def build_metadata(
    metadata: Mapping[str, object], description: str | None, declared_by: str
) -> dict[str, object]:
    """Return ``metadata`` with ``description`` under the key the dumpers read it from.

    Args:
        metadata: The metadata declared.
        description: The description declared, if any.
        declared_by: How the declaration is written, named in the error.

    Raises:
        LogicError: If both declare a description: neither would be the one
            meant.
    """
    if description is None:
        return dict(metadata)

    if "description" in metadata:
        raise LogicError(
            f'The "description" argument of "{declared_by}" cannot be used together with a '
            '"description" key in its "metadata" argument.'
        )

    return {**metadata, "description": description}
