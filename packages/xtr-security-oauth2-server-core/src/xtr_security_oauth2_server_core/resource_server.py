"""What an API puts in front of its routes to find out who is calling."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_oauth2_server_core.authorization_validators.authorization_validator_interface import (  # noqa: E501, TC001 -- one dotted path; container hydrates this constructor at runtime
    AuthorizationValidatorInterface,
)
from xtr_security_oauth2_server_core.repositories.access_token_repository_interface import (  # noqa: TC001 -- container hydrates this constructor at runtime
    AccessTokenRepositoryInterface,
)

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["ResourceServer"]


@final
class ResourceServer:
    """Turns a request carrying a token into one that knows whose token it is.

    This is the whole of the resource-server side: an API hands a request over
    and gets back the same request annotated with the token's identifier, the
    client, the resource owner and the scopes — or a refusal it answers with
    401. Everything that decides *how* a token is read lives in the validator,
    so a deployment changing the scheme or the profile of token it accepts
    changes what it builds this with and nothing else.

    It takes the access-token store beside the validator although the validator
    is what reads it, because the two belong to one deployment: a resource
    server answering for one store while its validator judges revocation
    against another would accept tokens the store says are withdrawn, and
    naming both in one constructor is what makes that mismatch something a
    reader sees.
    """

    __slots__ = ("_access_token_repository", "_authorization_validator")

    def __init__(
        self,
        access_token_repository: AccessTokenRepositoryInterface,
        authorization_validator: AuthorizationValidatorInterface,
    ) -> None:
        """Answer for ``access_token_repository``, reading through ``authorization_validator``."""
        self._access_token_repository: AccessTokenRepositoryInterface = access_token_repository
        self._authorization_validator: AuthorizationValidatorInterface = authorization_validator

    async def validate_authenticated_request(
        self,
        request: ServerRequestInterface,
    ) -> ServerRequestInterface:
        """Return ``request`` annotated with what the token it carries says.

        Raises:
            OAuthServerError: ``access_denied`` when the request carries no
                usable token.
        """
        return await self._authorization_validator.validate_authorization(request)

    @override
    def __repr__(self) -> str:
        """Name the validator by type alone, and nothing it or the store holds."""
        validator = type(self._authorization_validator).__name__

        return f"{type(self).__name__}(authorization_validator={validator})"
