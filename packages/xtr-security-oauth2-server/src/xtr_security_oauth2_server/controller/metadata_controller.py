"""The endpoint a client reads to find out what this server can do."""

from __future__ import annotations

import dataclasses
import json
from collections.abc import (  # noqa: TC003 -- container hydrates this constructor at runtime
    Hashable,
    Mapping,
)
from http import HTTPStatus
from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_oauth2_server.authorization_server_metadata import (  # noqa: TC001 -- container hydrates this constructor at runtime
    AuthorizationServerMetadata,
)
from xtr_security_oauth2_server.metadata_contributor_interface import (  # noqa: TC001 -- container hydrates this constructor at runtime
    MetadataContributorInterface,
)

if TYPE_CHECKING:
    from xtr_http_kernel.bridge import Response
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["MetadataController"]


@final
class MetadataController:
    """Publishes what this server is, where its endpoints are and what it accepts.

    A client that has only the issuer's name needs to find out where to send
    people, where to exchange a code, which scopes exist and which proof-key
    methods are accepted. This is the one document that says all of it, at the
    one place under the issuer a client knows to look.

    The document itself is settled when the container is built — it is made of
    the deployment's configuration and nothing a request can change — so it is
    held ready and only the extension fields are gathered per request. An
    extension contributing a field cannot take over one this server decides:
    the document merges contributions underneath its own answers.

    It answers ``404`` when the deployment has not enabled it, for the same
    reason the device-code endpoint does.
    """

    __slots__ = ("_contributors", "_document", "_enabled")

    def __init__(
        self,
        document: AuthorizationServerMetadata,
        contributors: Mapping[Hashable, MetadataContributorInterface],
        enabled: bool,
        contributor_qualifiers: tuple[str, ...] = (),
    ) -> None:
        """Publish ``document``, merging what ``contributors`` add, unless not ``enabled``.

        Args:
            document: What this deployment says about itself, already built.
            contributors: Every registered contributor, by the qualifier it was
                collected under.
            enabled: Whether this server describes itself at all.
            contributor_qualifiers: Those qualifiers in the order their
                priority put them — highest first, so that two contributing one
                field have a defined winner. Filled in by the compiler pass that
                collected them.
        """
        self._document = document
        self._contributors = tuple(
            contributors[qualifier]
            for qualifier in contributor_qualifiers
            if qualifier in contributors
        )
        self._enabled = enabled

    async def index_action(
        self,
        request: ServerRequestInterface,
        response: Response,
    ) -> Response:
        """Answer with the document describing this server."""
        del request
        if not self._enabled:
            return response.with_status(HTTPStatus.NOT_FOUND)
        published = self._document
        contributed = self._contributed()
        if contributed:
            published = dataclasses.replace(published, extra=contributed)
        answer = response.with_status(HTTPStatus.OK).with_header(
            "content-type",
            "application/json",
        )
        _ = answer.get_body().write(json.dumps(dict(published.to_dict())).encode())

        return answer

    def _contributed(self) -> Mapping[str, object]:
        """Return the extension fields, the highest-priority contributor winning."""
        merged: dict[str, object] = {}
        for contributor in self._contributors:
            for name, value in contributor.get_metadata().items():
                _ = merged.setdefault(name, value)

        return merged

    @override
    def __repr__(self) -> str:
        """Name the type and whether the endpoint is enabled, which is configuration."""
        return f"{type(self).__name__}(enabled={self._enabled!r})"
