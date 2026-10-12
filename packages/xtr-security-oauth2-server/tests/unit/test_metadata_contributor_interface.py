"""The contract an extension adds a field to this server's description through."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_oauth2_server.metadata_contributor_interface import (
    MetadataContributorInterface,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


@final
class _Contributor(MetadataContributorInterface):
    """What an add-on registers, saying it added a capability."""

    @override
    def get_metadata(self) -> Mapping[str, object]:
        return {"userinfo_endpoint": "https://auth.test/userinfo"}


def test_anything_answering_with_fields_satisfies_the_contract() -> None:
    # Checked at runtime, because the pass that collects contributors is
    # handed whatever an application registered.
    assert isinstance(_Contributor(), MetadataContributorInterface)


def test_something_that_answers_with_nothing_does_not() -> None:
    assert not isinstance(object(), MetadataContributorInterface)


def test_a_contributor_answers_with_the_fields_it_publishes() -> None:
    assert dict(_Contributor().get_metadata()) == {
        "userinfo_endpoint": "https://auth.test/userinfo",
    }
