"""A grant of this application's own, answering a name a shipped grant has.

Registered as a plain class, which is the documented way an application or an
add-on contributes a flow: being nominally a grant is enough for the container
to tag it, and the grant pass then hands it to the authorization server.

It builds on the abstract base rather than on a shipped grant, because every
shipped grant but the authorization-code one is final — and it inherits its
constructor, so this is also what proves a contributed grant can be built at
all: the two services that constructor reads have to be resolvable at runtime
for the container to hydrate it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_dependency_injection import as_service
from xtr_security_oauth2_server_core.grant.abstract_grant import AbstractGrant
from xtr_security_oauth2_server_core.oauth2_grants import OAuth2Grants

if TYPE_CHECKING:
    from datetime import timedelta

    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_oauth2_server_core.response_types.response_type_interface import (
        ResponseTypeInterface,
    )

__all__ = ["ClashingGrant"]


@final
@as_service
class ClashingGrant(AbstractGrant):
    """A grant answering ``client_credentials``, which the shipped one also answers.

    Nothing here gives it a name of its own, and that is the point: one name
    has to mean one flow, so a deployment running both is told rather than
    quietly left with whichever was registered last.
    """

    @override
    def get_identifier(self) -> str:
        """Answer for the same name the shipped client-credentials grant does."""
        return OAuth2Grants.CLIENT_CREDENTIALS

    @override
    async def respond_to_access_token_request(
        self,
        request: ServerRequestInterface,
        response_type: ResponseTypeInterface,
        access_token_ttl: timedelta,
    ) -> ResponseTypeInterface:
        """Never reached: the clash is refused while the server is assembled."""
        raise NotImplementedError
