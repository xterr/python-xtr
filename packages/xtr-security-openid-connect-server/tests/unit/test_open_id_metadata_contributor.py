"""The contributor adds what an OpenID Connect client discovers to the server's description."""

from __future__ import annotations

from typing import Final

from xtr_security_oauth2_server.metadata_contributor_interface import (
    MetadataContributorInterface,
)

from tests.support.signing import ISSUER
from xtr_security_openid_connect_server.claim_extractor import ClaimExtractor
from xtr_security_openid_connect_server.entities.claim_set_entity import ClaimSetEntity
from xtr_security_openid_connect_server.open_id_metadata_contributor import (
    OpenIdMetadataContributor,
)

#: Every claim the protocol's four claim sets name, beside the ID token's own.
#: ``profile`` and ``address`` are claims as well as scopes; ``phone`` is only a
#: scope, so it is not here.
PROTOCOL_CLAIMS: Final = sorted(
    {
        "sub",
        "iss",
        "aud",
        "exp",
        "iat",
        "auth_time",
        "nonce",
        "name",
        "family_name",
        "given_name",
        "middle_name",
        "nickname",
        "preferred_username",
        "profile",
        "picture",
        "website",
        "gender",
        "birthdate",
        "zoneinfo",
        "locale",
        "updated_at",
        "email",
        "email_verified",
        "address",
        "phone_number",
        "phone_number_verified",
    },
)


def _contributor(
    extractor: ClaimExtractor | None = None,
    issuer: str | None = ISSUER,
) -> OpenIdMetadataContributor:
    return OpenIdMetadataContributor(
        extractor if extractor is not None else ClaimExtractor(),
        issuer,
        "PS384",
    )


def test_it_is_a_metadata_contributor() -> None:
    assert isinstance(_contributor(), MetadataContributorInterface)


def test_the_supported_claims_are_every_claim_name_sorted_and_no_scope_name() -> None:
    claims = _contributor().get_metadata()["claims_supported"]

    assert claims == PROTOCOL_CLAIMS


def test_a_claim_set_added_after_the_build_is_published_too() -> None:
    extractor = ClaimExtractor()
    contributor = _contributor(extractor)

    extractor.add_claim_set(ClaimSetEntity("company", ("company_id",)))
    claims = contributor.get_metadata()["claims_supported"]

    assert claims == sorted([*PROTOCOL_CLAIMS, "company_id"])


def test_the_signing_algorithm_is_the_one_it_was_given() -> None:
    assert _contributor().get_metadata()["id_token_signing_alg_values_supported"] == ["PS384"]


def test_only_public_subject_identifiers_are_published() -> None:
    assert _contributor().get_metadata()["subject_types_supported"] == ["public"]


def test_the_request_parameters_this_server_does_not_read_are_published_unsupported() -> None:
    metadata = _contributor().get_metadata()

    assert metadata["claims_parameter_supported"] is False
    assert metadata["request_parameter_supported"] is False
    assert metadata["request_uri_parameter_supported"] is False


def test_outside_a_served_request_no_userinfo_endpoint_is_published() -> None:
    # Nothing is mounted to find the endpoint's path in.
    assert "userinfo_endpoint" not in _contributor().get_metadata()


def test_with_no_issuer_no_userinfo_endpoint_is_published() -> None:
    assert "userinfo_endpoint" not in _contributor(issuer=None).get_metadata()


def test_its_representation_names_the_issuer_and_the_algorithm() -> None:
    assert repr(_contributor()) == (
        f"OpenIdMetadataContributor(issuer={ISSUER!r}, signature_algorithm='PS384')"
    )
