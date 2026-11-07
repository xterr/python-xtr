"""The repository's own relying party, reading what the served provider answered.

The provider is checked against an implementation it shares no code with: the
OpenID Connect client side of xtr-security-http — its discovery reader, its
signature verifier, its ID-token claim checks and its userinfo reader.

Nothing that relying party reads is written here. Every document is fetched
from the served application first, over ASGI, exactly as it went over the wire
— status, headers and body — and a scripted HTTP client then answers each
request of the relying party with the captured answer for that path. The
paths of the key set and the userinfo endpoint are the ones the discovery
document announces, so a provider publishing the wrong one is caught.

Every cache the readers take is an in-memory one on a frozen clock.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, cast, final
from urllib.parse import urlsplit

from xtr_cache import ArrayAdapter
from xtr_http_client import MockHttpClient
from xtr_http_client.response import MockResponse
from xtr_security_http.access_token.oidc.oidc_user_info_token_handler import (
    OidcUserInfoTokenHandler,
)
from xtr_security_http.oidc.oidc_discovery import OidcDiscovery
from xtr_security_http.oidc.oidc_id_token import OidcIdToken
from xtr_security_http.oidc.oidc_signature_verifier import OidcSignatureVerifier

from tests.support.signing import ISSUER, make_clock

if TYPE_CHECKING:
    from collections.abc import Mapping

    import httpx
    from xtr_http_client_contracts import RequestOptions

__all__ = ["CONFIGURATION_PATH", "RelyingParty", "ServedAnswer", "relying_party_of"]

#: Where the provider's configuration document is read, under the issuer.
CONFIGURATION_PATH: Final = "/.well-known/openid-configuration"


@final
@dataclass(frozen=True, slots=True)
class ServedAnswer:
    """One answer of the served provider, as it went over the wire."""

    status: int
    headers: Mapping[str, str]
    body: bytes

    def replayed(self) -> MockResponse:
        """Return a fresh scripted response carrying this answer."""
        return MockResponse(
            self.body,
            {"http_code": self.status, "response_headers": dict(self.headers)},
        )


def _captured(answer: httpx.Response) -> ServedAnswer:
    return ServedAnswer(answer.status_code, dict(answer.headers), answer.content)


@final
class RelyingParty:
    """The relying-party readers, wired over the captured answers of one provider.

    Attributes:
        http_client: The scripted client every reader goes through.
        discovery: Reads the configuration document, checking its issuer.
        signature_verifier: Verifies a token against the published key set,
            keeping only the keys marked for signatures.
        id_token: Validates the claims of a verified ID token.
        user_info: Reads the userinfo endpoint the document announces.
    """

    __slots__ = (
        "_answers",
        "discovery",
        "http_client",
        "id_token",
        "signature_verifier",
        "user_info",
    )

    def __init__(self, answers: Mapping[str, ServedAnswer], algorithm: str) -> None:
        """Wire the readers over ``answers``, by path, accepting ``algorithm`` signatures."""
        self._answers = dict(answers)
        self.http_client = MockHttpClient(self._answer, base_uri=ISSUER)
        self.discovery = OidcDiscovery(self.http_client, _cache(), issuer=ISSUER)
        self.signature_verifier = OidcSignatureVerifier(
            self.discovery,
            _cache(),
            self.http_client,
            algorithms=(algorithm,),
        )
        self.id_token = OidcIdToken()
        self.user_info = OidcUserInfoTokenHandler(self.http_client)
        self.user_info.enable_discovery(_cache(), "userinfo")

    def _answer(self, method: str, url: str, options: RequestOptions) -> MockResponse:
        """Replay what the provider answered at ``url``'s path; a path it never served is 404."""
        del method, options
        served = self._answers.get(urlsplit(url).path)
        if served is None:
            return MockResponse(b"", {"http_code": 404})
        return served.replayed()


async def relying_party_of(
    client: httpx.AsyncClient,
    algorithm: str,
    access_token: str | None = None,
) -> RelyingParty:
    """Return the relying party over what the provider ``client`` reaches answers.

    The configuration document is fetched first; when it answered, the key set
    and — given ``access_token`` — the userinfo answer are fetched where it
    says they are.
    """
    configuration = await client.get(CONFIGURATION_PATH)
    answers = {CONFIGURATION_PATH: _captured(configuration)}
    if configuration.status_code == 200:
        document = cast("Mapping[str, object]", json.loads(configuration.content))
        jwks = urlsplit(str(document["jwks_uri"])).path
        answers[jwks] = _captured(await client.get(jwks))
        if access_token is not None:
            userinfo = urlsplit(str(document["userinfo_endpoint"])).path
            answers[userinfo] = _captured(
                await client.get(userinfo, headers={"authorization": f"Bearer {access_token}"}),
            )

    return RelyingParty(answers, algorithm)


def _cache() -> ArrayAdapter:
    """Return an in-memory cache on a frozen clock."""
    return ArrayAdapter(clock=make_clock())
