"""What an OpenID Connect client discovers about this provider, beyond the server's own fields."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast, final

from typing_extensions import override
from xtr_dependency_injection.exception import FastapiIntegrationError
from xtr_dependency_injection.integration.fastapi import current_connection
from xtr_security_oauth2_server.metadata_contributor_interface import (
    MetadataContributorInterface,
)
from xtr_security_oauth2_server.routing import paths_by_endpoint

from xtr_security_openid_connect_server.claim_extractor import (
    ClaimExtractor,  # noqa: TC001 -- container hydrates this constructor at runtime
)
from xtr_security_openid_connect_server.routing import userinfo

if TYPE_CHECKING:
    from collections.abc import Mapping

    from starlette.applications import Starlette

__all__ = ["OpenIdMetadataContributor"]

#: The claims an ID token itself carries, whichever scopes were granted.
_ID_TOKEN_CLAIMS: Final = ("sub", "iss", "aud", "exp", "iat", "auth_time", "nonce")


@final
class OpenIdMetadataContributor(MetadataContributorInterface):
    """Adds the provider's fields to the authorization server's description.

    One document describes both: a client discovering the provider reads the
    server's endpoints, scopes and flows there, and these fields beside them —
    where the userinfo endpoint is, which subject identifiers and signature
    algorithm ID tokens come with, which claims can be revealed, and which
    request parameters this provider does not read.

    The supported claims are claim names, never scope names: every name the
    claim sets hold, and the ones every ID token carries.

    The userinfo endpoint is published at the path its route has in the
    application being served, found by the endpoint function it calls, so one
    a routes file moved is published where it now is. It is read on every
    call — the authorization server reads its own paths once — so the
    contributor can be shared by every request; outside a served request
    nothing is mounted, and with no issuer there is nothing to build the URL
    from, so the field is left out.
    """

    __slots__ = ("_claim_extractor", "_issuer", "_signature_algorithm")

    def __init__(
        self,
        claim_extractor: ClaimExtractor,
        issuer: str | None,
        signature_algorithm: str,
    ) -> None:
        """Describe the provider whose claim sets ``claim_extractor`` holds.

        Args:
            claim_extractor: Holds every claim set, so every claim the
                provider can reveal.
            issuer: The origin the provider is known by, or ``None`` when the
                deployment has not named it.
            signature_algorithm: What ID tokens are signed with.
        """
        self._claim_extractor = claim_extractor
        self._issuer = issuer
        self._signature_algorithm = signature_algorithm

    @override
    def get_metadata(self) -> Mapping[str, object]:
        """Return the provider's fields, the userinfo endpoint's where it is served."""
        names: set[str] = set(_ID_TOKEN_CLAIMS)
        for claim_set in self._claim_extractor.get_claim_sets():
            names.update(claim_set.get_claim_names())
        metadata: dict[str, object] = {}
        path = self._userinfo_path()
        if self._issuer is not None and path is not None:
            metadata["userinfo_endpoint"] = f"{self._issuer}{path}"
        metadata.update(
            {
                "subject_types_supported": ["public"],
                "id_token_signing_alg_values_supported": [self._signature_algorithm],
                "claims_supported": sorted(names),
                "claims_parameter_supported": False,
                "request_parameter_supported": False,
                "request_uri_parameter_supported": False,
            },
        )

        return metadata

    @override
    def __repr__(self) -> str:
        """Name the issuer and the algorithm, which are configuration."""
        return (
            f"{type(self).__name__}(issuer={self._issuer!r}, "
            f"signature_algorithm={self._signature_algorithm!r})"
        )

    @staticmethod
    def _userinfo_path() -> str | None:
        """Return where the application being served mounts the userinfo endpoint, if anywhere."""
        try:
            app = cast("Starlette", current_connection().app)
        except FastapiIntegrationError:
            return None
        return paths_by_endpoint(app.routes).get(userinfo)
