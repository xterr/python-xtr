"""The reference and variables of a template a mail provider hosts and renders."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, final

from typing_extensions import override

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["RemoteTemplate"]


@final
class RemoteTemplate:
    """A template hosted by the mail provider: which one, and the variables it is rendered with.

    The reference is whatever the provider names a template by — an id, a name, an alias. The
    variables are copied in and out: the template does not change once made.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_reference", "_variables")

    def __init__(self, reference: str, variables: Mapping[str, object] | None = None) -> None:
        """Keep ``reference`` and a copy of ``variables``."""
        self._reference: str = reference
        self._variables: dict[str, object] = dict(variables or {})

    def get_reference(self) -> str:
        """Return the provider-side reference of the template."""
        return self._reference

    def get_variables(self) -> dict[str, object]:
        """Return a copy of the variables the provider renders the template with."""
        return dict(self._variables)

    @override
    def __repr__(self) -> str:
        """Show the reference and the variables."""
        return f"RemoteTemplate({self._reference!r}, {self._variables!r})"
