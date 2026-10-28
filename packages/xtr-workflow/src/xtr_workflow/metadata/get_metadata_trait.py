"""Reading one metadata entry by subject, for a store that reads whole mappings."""

from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING

from typing_extensions import override

from xtr_workflow.exception import InvalidArgumentError
from xtr_workflow.transition import Transition

from .metadata_store_interface import MetadataStoreInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["GetMetadataTrait"]


class GetMetadataTrait(MetadataStoreInterface, ABC):
    """Implements :meth:`get_metadata` on a store's three getters.

    A store derives from this and implements :meth:`get_workflow_metadata`,
    :meth:`get_place_metadata` and :meth:`get_transition_metadata`; reading
    one entry by subject comes with it, the same for every store, so no store
    has to tell a place from a transition itself.
    """

    @override
    def get_metadata(self, key: str, subject: str | Transition | None = None) -> object | None:
        """Return one entry of the metadata of the workflow, of a place or of a transition.

        Args:
            key: The name of the entry.
            subject: ``None`` for the workflow, a place name for that place, or
                a transition for that transition.

        Returns:
            The entry, or ``None`` when the subject's metadata has none by that name.

        Raises:
            InvalidArgumentError: If ``subject`` is none of the three.
        """
        return self._metadata_of(subject).get(key)

    def _metadata_of(self, subject: object) -> Mapping[str, object]:
        """Return the metadata ``subject`` stands for.

        Typed loosely on purpose: a caller ignoring the annotations can hand
        over anything, and this is where it is refused.

        Raises:
            InvalidArgumentError: If ``subject`` is neither ``None``, a place
                name nor a transition.
        """
        match subject:
            case None:
                return self.get_workflow_metadata()
            case str():
                return self.get_place_metadata(subject)
            case Transition():
                return self.get_transition_metadata(subject)
            case _:
                raise InvalidArgumentError(
                    "Could not find a MetadataBag for the subject of type "
                    f'"{type(subject).__name__}".'
                )
