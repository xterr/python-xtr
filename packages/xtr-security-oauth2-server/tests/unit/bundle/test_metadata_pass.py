"""The contributors to this server's description, gathered in the order they win in."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

import pytest
from typing_extensions import override

from tests.support.building import processing_builder
from xtr_security_oauth2_server.controller.metadata_controller import MetadataController
from xtr_security_oauth2_server.exception import InvalidConfigurationError
from xtr_security_oauth2_server.metadata_contributor_interface import (
    MetadataContributorInterface,
)
from xtr_security_oauth2_server.null_metadata_contributor import NullMetadataContributor

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_dependency_injection import ContainerBuilder

from xtr_security_oauth2_server.bundle.metadata_pass import METADATA_TAG, MetadataPass


@final
class _Loud(MetadataContributorInterface):
    """A contributor an add-on would register."""

    @override
    def get_metadata(self) -> Mapping[str, object]:
        return {"loud": True}


@final
class _Quiet(MetadataContributorInterface):
    """Another, so an order between two can be asserted on."""

    @override
    def get_metadata(self) -> Mapping[str, object]:
        return {"quiet": True}


def _with_endpoint() -> ContainerBuilder:
    """Return a builder holding the description endpoint, as the bundle registers it."""
    builder = processing_builder()
    _ = builder.register(MetadataController)

    return builder


def _qualifiers(builder: ContainerBuilder) -> tuple[str, ...]:
    """Return the order the endpoint was told to read its contributors in."""
    read = builder.get_definition(MetadataController).arguments["contributor_qualifiers"]
    assert isinstance(read, tuple)

    return cast("tuple[str, ...]", read)


def test_with_no_contributor_tagged_the_endpoint_is_left_alone() -> None:
    builder = _with_endpoint()

    MetadataPass().process(builder)

    assert "contributor_qualifiers" not in builder.get_definition(MetadataController).arguments


def test_with_no_endpoint_registered_nothing_is_gathered() -> None:
    # Nothing to contribute to; whatever left the endpoint unregistered reports
    # itself.
    builder = processing_builder()
    _ = builder.register(NullMetadataContributor).add_tag(METADATA_TAG)

    MetadataPass().process(builder)

    assert not builder.has_alias(MetadataContributorInterface, "oauth2_server_metadata_0")


def test_every_tagged_contributor_is_reachable_under_its_own_qualifier() -> None:
    builder = _with_endpoint()
    _ = builder.register(NullMetadataContributor).add_tag(METADATA_TAG)
    _ = builder.register(_Loud).add_tag(METADATA_TAG)

    MetadataPass().process(builder)

    assert len(_qualifiers(builder)) == 2
    for qualifier in _qualifiers(builder):
        assert builder.has_alias(MetadataContributorInterface, qualifier)


def test_the_higher_priority_contributor_is_read_first() -> None:
    # Which matters only when two publish the same field: then the one a
    # deployment put first wins, rather than whichever happened to register
    # first.
    builder = _with_endpoint()
    _ = builder.register(_Quiet).add_tag(METADATA_TAG)
    _ = builder.register(_Loud).add_tag(METADATA_TAG, priority=10)

    MetadataPass().process(builder)

    first = builder.get_alias(MetadataContributorInterface, _qualifiers(builder)[0])
    assert first[0] is _Loud


def test_a_priority_that_is_not_a_whole_number_is_refused_naming_the_contributor() -> None:
    builder = _with_endpoint()
    _ = builder.register(_Loud).add_tag(METADATA_TAG, priority="first")

    with pytest.raises(InvalidConfigurationError) as refused:
        MetadataPass().process(builder)

    message = str(refused.value)
    assert "_Loud" in message
    assert "'first'" in message


def test_a_priority_given_as_a_flag_is_refused_too() -> None:
    # ``True`` is an int to Python and a mistake to a reader.
    builder = _with_endpoint()
    _ = builder.register(_Loud).add_tag(METADATA_TAG, priority=True)

    with pytest.raises(InvalidConfigurationError, match=r"_Loud"):
        MetadataPass().process(builder)
