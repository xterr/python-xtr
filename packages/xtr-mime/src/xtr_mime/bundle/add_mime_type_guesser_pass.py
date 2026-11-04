"""Hands the container's MIME types table every guesser tagged for it, in the order it asks them."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final, final

from typing_extensions import override
from xtr_dependency_injection import CompilerPassInterface, ContainerBuilder, ServiceKey

from xtr_mime.exception import LogicError
from xtr_mime.mime_type_guesser_interface import MimeTypeGuesserInterface
from xtr_mime.mime_types import MimeTypes

__all__ = ["MIME_TYPE_GUESSER_TAG", "AddMimeTypeGuesserPass"]

MIME_TYPE_GUESSER_TAG: Final = "mime.mime_type_guesser"
"""The tag a guesser carries to be asked by the container's table.

It takes one optional attribute, ``priority`` — an ``int``, higher asked first; without it, the
definition's own priority, or 0. A class subclassing ``MimeTypeGuesserInterface`` carries it
without being told; a bundle tagging one explicitly gives the priority it needs::

    services.set(UploadGuesser).add_tag(MIME_TYPE_GUESSER_TAG, priority=10)
"""

_QUALIFIER_PREFIX: Final = "mime.guesser."
"""What the qualifier each tagged guesser is offered to the table under starts with."""


@final
class AddMimeTypeGuesserPass(CompilerPassInterface):
    """Registers every service tagged :data:`MIME_TYPE_GUESSER_TAG` with the table.

    The guessers are ordered by priority, highest first, then by the order they were
    registered in; the table asks them in that order, and answers from the file's extension
    only when none of them does. Each is offered to the table under a qualifier of its own,
    ``mime.guesser.<index>``, and the table's factory is handed those qualifiers: it builds the
    guessers when the table is built, and is never handed the container.

    The table is a guesser itself, so autoconfiguration tags its definition; the pass takes
    that tag off. A service decorating another is asked as the service it decorates, which
    carries the tag.
    """

    __slots__ = ()

    @override
    def process(self, builder: ContainerBuilder) -> None:
        """Offer every tagged guesser to the table.

        Raises:
            LogicError: When a tag's priority is not an integer.
        """
        _ = builder.get_definition(MimeTypes).clear_tag(MIME_TYPE_GUESSER_TAG)
        ranked: list[tuple[ServiceKey, int]] = []
        for key, attribute_list in builder.find_tagged_service_ids(MIME_TYPE_GUESSER_TAG).items():
            definition = builder.get_definition(*key)
            if definition.decorates is None:
                ranked.append((key, _priority(key, attribute_list, definition.priority or 0)))
        ranked.sort(key=lambda one: -one[1])

        names: list[str] = []
        for index, ((service, qualifier), _) in enumerate(ranked):
            name = f"{_QUALIFIER_PREFIX}{index}"
            builder.set_alias(
                MimeTypeGuesserInterface,
                service,
                alias_qualifier=name,
                target_qualifier=qualifier,
            )
            names.append(name)
        _ = builder.get_definition(MimeTypes).set_argument("guesser_names", names)


def _priority(
    key: ServiceKey, attribute_list: Sequence[Mapping[str, object]], fallback: int
) -> int:
    """Return the highest priority the service's tags give, else ``fallback``.

    A service tagged explicitly and by autoconfiguration carries the tag twice, once without a
    priority; the explicit one decides.

    Raises:
        LogicError: When a priority is not an integer.
    """
    priorities: list[int] = []
    for attributes in attribute_list:
        if "priority" not in attributes:
            continue
        priority = attributes["priority"]
        if not isinstance(priority, int) or isinstance(priority, bool):
            service = key[0].__qualname__ + ("" if key[1] is None else f"[{key[1]!r}]")
            raise LogicError(
                f"{service} is tagged {MIME_TYPE_GUESSER_TAG!r} with a priority that is not an "
                f"integer"
            )
        priorities.append(priority)
    return max(priorities, default=fallback)
