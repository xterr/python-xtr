"""The endpoint a resource server reads this server's verifying keys from."""

from __future__ import annotations

import json
from http import HTTPStatus
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_security_jwt.exception import MissingKeyError
from xtr_security_jwt.services.key_loader import public_key_set

from xtr_security_oauth2_server._missing_key_file import missing_key_file

if TYPE_CHECKING:
    from xtr_http_kernel.bridge import Response
    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_jwt.services.key_loader import KeyLoaderInterface

__all__ = ["JwksController"]


@final
class JwksController:
    """Publishes the public half of what this server signs its access tokens with.

    An access token is a signed document, so anything that reads one needs the
    key to check the signature against. Publishing the key set is what lets a
    resource server — written by somebody else, deployed somewhere else — read
    tokens without a key being copied around by hand.

    The set holds the key being signed with now and every key the deployment
    still trusts, each under the id a token's header names it by, so a key can
    be rotated without a flag day: the new key is published, tokens start being
    signed with it, and the old one stays in the set until the last token signed
    with it has expired.

    Only public halves are ever written. The set is built from the signing key's
    public half rather than from a separately configured copy, so the published
    set cannot drift from what is actually signing.
    """

    __slots__ = ("_key_loader", "_signature_algorithm")

    def __init__(self, key_loader: KeyLoaderInterface, signature_algorithm: str) -> None:
        """Publish ``key_loader``'s keys, read as keys of ``signature_algorithm``."""
        self._key_loader = key_loader
        self._signature_algorithm = signature_algorithm

    async def index_action(
        self,
        request: ServerRequestInterface,
        response: Response,
    ) -> Response:
        """Answer with the key set this server's tokens are verified against.

        Raises:
            InvalidConfigurationError: When the signing key file is not there —
                taken away since the server started, since starting reads it.
        """
        del request
        try:
            published = public_key_set(self._key_loader, self._signature_algorithm)
        except MissingKeyError as missing:
            raise missing_key_file(
                missing,
                "authorization_server.private_key",
                "this server has no key set to publish",
            ) from missing
        answer = response.with_status(HTTPStatus.OK).with_header(
            "content-type",
            "application/jwk-set+json",
        )
        _ = await answer.get_body().write(json.dumps(published).encode())

        return answer

    @override
    def __repr__(self) -> str:
        """Name the type and the algorithm, never the keys or where they are kept."""
        return f"{type(self).__name__}(signature_algorithm={self._signature_algorithm!r})"
