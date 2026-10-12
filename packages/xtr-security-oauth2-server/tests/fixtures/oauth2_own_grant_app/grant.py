"""A grant of this application's own, under a name no shipped grant answers.

Registered as a plain class, which is the documented way an application
contributes a flow: being nominally a grant is enough for the container to tag
it, and the grant pass then hands it to the authorization server.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_dependency_injection import as_service
from xtr_security_oauth2_server_core.grant.abstract_grant import AbstractGrant

if TYPE_CHECKING:
    from datetime import timedelta

    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_oauth2_server_core.response_types.response_type_interface import (
        ResponseTypeInterface,
    )

__all__ = ["SERVICE_ACCOUNT", "ServiceAccountGrant"]

#: What a token request names this flow by: an extension grant type, which
#: RFC 6749 section 4.5 names with an absolute URI.
SERVICE_ACCOUNT: Final[str] = "urn:example:params:oauth:grant-type:service_account"


@final
@as_service
class ServiceAccountGrant(AbstractGrant):
    """A flow the deployment's settings know nothing about."""

    @override
    def get_identifier(self) -> str:
        """Answer for a name of its own."""
        return SERVICE_ACCOUNT

    @override
    async def respond_to_access_token_request(
        self,
        request: ServerRequestInterface,
        response_type: ResponseTypeInterface,
        access_token_ttl: timedelta,
    ) -> ResponseTypeInterface:
        """Never reached: only the description of this server is read."""
        raise NotImplementedError
