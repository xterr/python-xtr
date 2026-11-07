"""The endpoint a client reads the signed-in end-user's claims from."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_security_core.authentication.token.storage.token_storage_interface import (  # noqa: TC002 -- container hydrates this constructor at runtime
    TokenStorageInterface,
)
from xtr_security_oauth2_server.security.authentication.token.oauth2_token import OAuth2Token
from xtr_security_oauth2_server.security.user.client_credentials_user import (
    ClientCredentialsUser,
)
from xtr_security_oauth2_server_core.bearer_challenge import bearer_challenge
from xtr_security_oauth2_server_core.repositories.client_repository_interface import (  # noqa: TC002 -- container hydrates this constructor at runtime
    ClientRepositoryInterface,
)

from xtr_security_openid_connect_server.claim_extractor import (  # noqa: TC001 -- container hydrates this constructor at runtime
    ClaimExtractor,
)
from xtr_security_openid_connect_server.repositories.identity_provider_interface import (  # noqa: TC001 -- container hydrates this constructor at runtime
    IdentityProviderInterface,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_kernel.bridge import Response
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["UserInfoController"]

#: The scope a token must carry for the end-user it names to be described.
_OPENID_SCOPE: Final = "openid"

#: The one body a request posted here may carry (OpenID Connect Core 5.3.1).
_FORM_CONTENT_TYPE: Final = "application/x-www-form-urlencoded"

#: What every refused token is told. It says nothing of why: whether no token
#: came, or one issued to a client for itself, is not the caller's to learn.
_NO_END_USER: Final = "The access token does not stand for a signed-in end-user."


@final
class UserInfoController:
    """Answers the claims of the end-user an access token stands for.

    The token is the one the request's firewall settled on, read from the
    token storage; this endpoint reads no credential itself. That is what makes
    it fail closed: a deployment that put no firewall in front of it has no
    token in the storage, and every request is refused.

    Only a token a signed-in end-user granted is answered, and only when it was
    granted ``openid``: a token a client was issued for itself names nobody,
    and a token without ``openid`` was never meant to identify anyone. What is
    answered is the subject, then the claims the token's scopes reveal. The
    subject is the end-user the token was issued for, as the token names them:
    the identifier the ID token carried, which a client compares the answer's
    subject against (OpenID Connect Core 5.3.2). So it is answered first, and
    no claim of the identity provider's replaces it — not even one the
    provider calls ``sub``.

    Per-request: the token storage it reads is the request's own.
    """

    __slots__ = ("_claim_extractor", "_client_repository", "_identity_provider", "_token_storage")

    def __init__(
        self,
        token_storage: TokenStorageInterface,
        client_repository: ClientRepositoryInterface,
        identity_provider: IdentityProviderInterface,
        claim_extractor: ClaimExtractor,
    ) -> None:
        """Answer from the token in ``token_storage``, describing users ``identity_provider`` finds.

        Args:
            token_storage: Where the request's firewall left the token it read.
            client_repository: Where the client the token was issued to is
                found, to hand the identity provider along with the user.
            identity_provider: Finds the end-user and the claims they hold.
            claim_extractor: Picks the claims the token's scopes reveal.
        """
        self._token_storage = token_storage
        self._client_repository = client_repository
        self._identity_provider = identity_provider
        self._claim_extractor = claim_extractor

    async def index_action(self, request: ServerRequestInterface, response: Response) -> Response:
        """Answer ``request`` with the end-user's claims, or the refusal it is owed."""
        if request.get_method() == "POST" and not _is_form(request):
            return await _refused(
                response,
                400,
                "invalid_request",
                "A request posted here carries a form-encoded body, or none.",
            )
        token = self._token_storage.get_token()
        if not isinstance(token, OAuth2Token) or isinstance(
            token.get_user(), ClientCredentialsUser
        ):
            return await _refused(response, 401, "invalid_token", _NO_END_USER)
        scopes = token.get_scopes()
        if _OPENID_SCOPE not in scopes:
            return await _refused(
                response,
                403,
                "insufficient_scope",
                "The access token was not granted the openid scope.",
                scope=_OPENID_SCOPE,
            )
        client = await self._client_repository.get_client_entity(token.get_oauth_client_id())
        if client is None:
            return await _refused(response, 401, "invalid_token", _NO_END_USER)
        subject = token.get_user_identifier()
        user = await self._identity_provider.get_user_entity_by_identifier(subject, client)
        claims = self._claim_extractor.extract(scopes, await user.get_claims())
        document = {"sub": subject} | {
            name: value for name, value in claims.items() if name != "sub"
        }

        return await _answered(response, 200, document)

    @override
    def __repr__(self) -> str:
        """Name the type; what it holds says nothing a reader needs."""
        return f"{type(self).__name__}()"


def _is_form(request: ServerRequestInterface) -> bool:
    """Tell whether ``request`` says its body is form-encoded, parameters aside."""
    media_type = request.get_header_line("Content-Type").partition(";")[0]

    return media_type.strip().lower() == _FORM_CONTENT_TYPE


async def _refused(
    response: Response,
    status: int,
    error: str,
    description: str,
    **challenge: str,
) -> Response:
    """Return the bearer refusal RFC 6750 section 3 describes, as a header and a document."""
    refusal = response.with_header(
        "www-authenticate",
        bearer_challenge("error", error, error_description=description, **challenge),
    )

    return await _answered(refusal, status, {"error": error, "error_description": description})


async def _answered(response: Response, status: int, document: Mapping[str, object]) -> Response:
    """Return ``document`` as a JSON answer carrying ``status`` that no cache may keep.

    An answer here describes one person, or refuses to; either is for the
    caller alone, never for a shared cache to hand to the next.
    """
    answer = (
        response.with_status(status)
        .with_header("content-type", "application/json")
        .with_header("cache-control", "no-store")
        .with_header("pragma", "no-cache")
    )
    _ = await answer.get_body().write(json.dumps(document, separators=(",", ":")).encode())

    return answer
