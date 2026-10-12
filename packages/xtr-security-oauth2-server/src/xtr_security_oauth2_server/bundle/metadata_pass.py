"""Collecting the extensions that add fields to this server's description."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_dependency_injection import CompilerPassInterface

from xtr_security_oauth2_server.controller.metadata_controller import MetadataController
from xtr_security_oauth2_server.exception.invalid_configuration_error import (
    InvalidConfigurationError,
)
from xtr_security_oauth2_server.metadata_contributor_interface import (
    MetadataContributorInterface,
)

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder, ServiceKey

__all__ = ["METADATA_TAG", "MetadataPass"]

#: The tag an extension's contributor carries to be published in this server's
#: description.
METADATA_TAG: Final = "oauth2_server.metadata"

#: The tag attribute ordering two contributors that would publish the same
#: field. Higher wins.
_PRIORITY_ATTRIBUTE: Final = "priority"

#: What a qualifier for a collected contributor is built from.
_QUALIFIER = "oauth2_server_metadata_{index}"


@final
class MetadataPass(CompilerPassInterface):
    """Hands the description endpoint every contributor, highest priority first.

    An extension that adds a capability has to say so where a client looks, and
    what it adds is not this package's to know. So each contributor is a
    service of its own, tagged, and this gathers them.

    The same shape as the grants: a tagged contributor is aliased under the
    contributor interface with a qualifier of its own, and the endpoint is
    given the ordered list of those qualifiers, which it resolves in that
    order. Ordering matters only when two contributors publish the same field —
    then the one with the higher priority wins, and a deployment can say which.

    The bundle always tags one contributor that adds nothing, so this collection
    is never empty: nothing can be injected as an empty collection, and the
    ordinary deployment has no extension at all.
    """

    @override
    def process(self, builder: ContainerBuilder) -> None:
        """Alias every tagged contributor and give the endpoint the order to read them in.

        Raises:
            InvalidConfigurationError: When a tag names a priority that is not
                a whole number.
        """
        tagged = builder.find_tagged_service_ids(METADATA_TAG)
        if not tagged or not builder.has_definition(MetadataController):
            # With no description endpoint there is nothing to contribute to;
            # the bundle reports whatever left it unregistered.
            return
        ordered = sorted(
            enumerate(tagged.items()),
            key=lambda entry: (-_priority_of(entry[1][1][0], entry[1][0]), entry[0]),
        )
        qualifiers: list[str] = []
        for index, (key, _tags) in ordered:
            qualifier = _QUALIFIER.format(index=index)
            builder.set_alias(
                MetadataContributorInterface,
                key[0],
                alias_qualifier=qualifier,
                target_qualifier=key[1],
            )
            qualifiers.append(qualifier)
        _ = builder.get_definition(MetadataController).set_argument(
            "contributor_qualifiers",
            tuple(qualifiers),
        )
        builder.log(self, f"Published {len(qualifiers)} metadata contributor(s).")


def _priority_of(attributes: dict[str, object], key: ServiceKey) -> int:
    """Return the priority the contributor ``key`` was tagged with, or zero.

    Raises:
        InvalidConfigurationError: When the tag names a priority that is not a
            whole number, which would make the order of two contributors
            undefined rather than merely surprising.
    """
    named = attributes.get(_PRIORITY_ATTRIBUTE, 0)
    if isinstance(named, bool) or not isinstance(named, int):
        raise InvalidConfigurationError(
            f"The metadata contributor {key[0].__qualname__} is tagged with a "
            f"{_PRIORITY_ATTRIBUTE} of {named!r}, which is not a whole number; tag it with an "
            "int, or leave it out for zero.",
        )

    return named
