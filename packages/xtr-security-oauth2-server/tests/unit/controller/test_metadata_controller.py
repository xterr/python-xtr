"""The document this server publishes about itself, and what an extension adds to it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

import pytest
from typing_extensions import override
from xtr_http_kernel.bridge import Response

from tests.support.messages import document_of, server_request
from xtr_security_oauth2_server.authorization_server_metadata import AuthorizationServerMetadata
from xtr_security_oauth2_server.controller.metadata_controller import MetadataController
from xtr_security_oauth2_server.metadata_contributor_interface import (
    MetadataContributorInterface,
)
from xtr_security_oauth2_server.null_metadata_contributor import NullMetadataContributor

if TYPE_CHECKING:
    from collections.abc import Hashable, Mapping

pytestmark = pytest.mark.anyio

_ISSUER: Final = "https://auth.test"
_NOT_FOUND: Final = 404


@final
class _Contributor(MetadataContributorInterface):
    """What an add-on registers to say it added a capability."""

    def __init__(self, fields: Mapping[str, object]) -> None:
        self._fields = fields

    @override
    def get_metadata(self) -> Mapping[str, object]:
        return self._fields


def _document() -> AuthorizationServerMetadata:
    """Return a minimal description, as the bundle builds one."""
    return AuthorizationServerMetadata(
        _ISSUER,
        {"token_endpoint": f"{_ISSUER}/token"},
        ("client_credentials",),
        ("read",),
        ("S256",),
    )


def _controller(
    contributors: Mapping[Hashable, MetadataContributorInterface],
    *,
    enabled: bool = True,
) -> MetadataController:
    """Return the endpoint reading ``contributors`` in the order given."""
    order = tuple(str(qualifier) for qualifier in contributors)

    return MetadataController(_document(), contributors, enabled, order)


async def _published(controller: MetadataController) -> Mapping[str, object]:
    """Return the document ``controller`` answers with."""
    answered = await controller.index_action(
        server_request("GET", "/.well-known/oauth-authorization-server"),
        Response(200),
    )
    document = document_of(answered)
    assert isinstance(document, dict)

    return {str(name): value for name, value in document.items()}  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType] -- a decoded document


async def test_a_deployment_that_did_not_enable_it_answers_not_found() -> None:
    answered = await _controller({}, enabled=False).index_action(
        server_request("GET", "/.well-known/oauth-authorization-server"),
        Response(200),
    )

    assert answered.get_status_code() == _NOT_FOUND


async def test_what_the_deployment_decided_itself_is_published() -> None:
    published = await _published(_controller({"none": NullMetadataContributor()}))

    assert published["issuer"] == _ISSUER
    assert published["token_endpoint"] == f"{_ISSUER}/token"


async def test_a_contributor_that_adds_nothing_changes_the_document_not_at_all() -> None:
    with_nothing = await _published(_controller({"none": NullMetadataContributor()}))
    alone = await _published(_controller({}))

    assert with_nothing == alone


async def test_a_contributed_field_reaches_the_document() -> None:
    published = await _published(
        _controller({"addon": _Contributor({"userinfo_endpoint": f"{_ISSUER}/userinfo"})}),
    )

    assert published["userinfo_endpoint"] == f"{_ISSUER}/userinfo"


async def test_the_contributor_read_first_wins_a_field_two_of_them_publish() -> None:
    # Which is what the priority on the tag is for: two extensions publishing
    # one field have a defined winner rather than whichever registered first.
    published = await _published(
        _controller(
            {
                "first": _Contributor({"ui_locales_supported": ["en"]}),
                "second": _Contributor({"ui_locales_supported": ["fr"]}),
            },
        ),
    )

    assert published["ui_locales_supported"] == ["en"]


async def test_a_contributor_cannot_take_over_what_this_server_decides() -> None:
    published = await _published(_controller({"addon": _Contributor({"issuer": "https://other"})}))

    assert published["issuer"] == _ISSUER


def test_a_qualifier_nothing_was_collected_under_is_left_out() -> None:
    # The pass fills the order in; a qualifier that names no contributor is a
    # collection that moved on, not a reason to fail a request.
    controller = MetadataController(_document(), {}, True, ("gone",))

    assert repr(controller) == "MetadataController(enabled=True)"


def test_it_says_whether_the_endpoint_is_enabled_and_nothing_else() -> None:
    assert repr(_controller({}, enabled=False)) == "MetadataController(enabled=False)"
