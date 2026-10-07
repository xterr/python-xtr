"""The OIDC token handler verifies a third-party token into a user badge."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override
from xtr_security_core.exception import InvalidArgumentError
from xtr_security_core.user.attributes_based_user_provider_interface import (
    AttributesBasedUserProviderInterface,
)
from xtr_security_core.user.in_memory_user import InMemoryUser
from xtr_security_core.user.oidc_user import OidcUser
from xtr_security_core.user.user_provider_interface import UserProviderInterface

from tests.support.oidc import (
    AUDIENCE,
    ISSUER,
    NOW,
    make_key,
    make_key_set,
    mint,
    public_jwks,
)
from xtr_security_http.access_token.oidc import (
    OidcTokenHandler,
    StaticOidcKeySetProvider,
)
from xtr_security_http.authenticator.oidc.oidc_jwks import (
    OidcKeySetProviderInterface,
)
from xtr_security_http.exception import InvalidAccessTokenError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from joserfc.jwk import KeySet, RSAKey
    from xtr_security_core.user.user_interface import UserInterface


def _provider_for(*keys: RSAKey) -> StaticOidcKeySetProvider:
    return StaticOidcKeySetProvider(public_jwks(*keys))


def _handler(  # noqa: PLR0913 -- a test builder; every knob defaults
    key: RSAKey,
    *,
    now: int = NOW,
    algorithms: tuple[str, ...] = ("RS256",),
    claim: str = "sub",
    leeway: int = 0,
    enforce_at_jwt_type: bool = False,
    user_provider: UserProviderInterface | None = None,
) -> OidcTokenHandler:
    return OidcTokenHandler(
        _provider_for(key),
        issuers=(ISSUER,),
        audience=AUDIENCE,
        algorithms=algorithms,
        claim=claim,
        leeway=leeway,
        enforce_at_jwt_type=enforce_at_jwt_type,
        clock=lambda: now,
        user_provider=user_provider,
    )


@pytest.mark.anyio
async def test_a_valid_token_yields_a_badge_with_scope_and_claims() -> None:
    key = make_key()
    handler = _handler(key)
    token = mint(key, extra={"scope": "books:read orders:read", "client_id": "web", "jti": "id-1"})

    badge = await handler.get_user_badge_from(token)

    assert badge.get_user_identifier() == "alice"
    attributes = badge.get_attributes()
    assert attributes["scope"] == ["books:read", "orders:read"]
    assert attributes["client_id"] == "web"
    assert attributes["jti"] == "id-1"
    assert isinstance(attributes["claims"], dict)


@pytest.mark.anyio
async def test_scopes_are_read_from_the_scp_list_when_scope_is_absent() -> None:
    key = make_key()
    handler = _handler(key)
    token = mint(key, extra={"scp": ["a", "b"]})

    badge = await handler.get_user_badge_from(token)

    assert badge.get_attributes()["scope"] == ["a", "b"]


@pytest.mark.anyio
async def test_an_expired_token_is_refused() -> None:
    key = make_key()
    handler = _handler(key, now=NOW + 5000)
    token = mint(key)

    with pytest.raises(InvalidAccessTokenError):
        _ = await handler.get_user_badge_from(token)


@pytest.mark.anyio
async def test_a_token_without_an_exp_claim_is_refused() -> None:
    key = make_key()
    handler = _handler(key)
    token = mint(key, include_exp=False)

    with pytest.raises(InvalidAccessTokenError):
        _ = await handler.get_user_badge_from(token)


@pytest.mark.anyio
async def test_a_leeway_admits_a_just_expired_token() -> None:
    key = make_key()
    handler = _handler(key, now=NOW + 3610, leeway=30)
    token = mint(key)

    badge = await handler.get_user_badge_from(token)

    assert badge.get_user_identifier() == "alice"


@pytest.mark.anyio
async def test_a_not_yet_valid_token_is_refused() -> None:
    key = make_key()
    handler = _handler(key)
    token = mint(key, nbf_offset=500)

    with pytest.raises(InvalidAccessTokenError):
        _ = await handler.get_user_badge_from(token)


@pytest.mark.anyio
async def test_a_token_from_an_untrusted_issuer_is_refused() -> None:
    key = make_key()
    handler = _handler(key)
    token = mint(key, issuer="https://evil.example")

    with pytest.raises(InvalidAccessTokenError):
        _ = await handler.get_user_badge_from(token)


@pytest.mark.anyio
async def test_a_token_for_another_audience_is_refused() -> None:
    key = make_key()
    handler = _handler(key)
    token = mint(key, audience="other-api")

    with pytest.raises(InvalidAccessTokenError):
        _ = await handler.get_user_badge_from(token)


@pytest.mark.anyio
async def test_a_token_signed_with_an_unknown_key_is_refused() -> None:
    signer = make_key("signer")
    trusted = make_key("trusted")
    handler = _handler(trusted)
    token = mint(signer)

    with pytest.raises(InvalidAccessTokenError):
        _ = await handler.get_user_badge_from(token)


@pytest.mark.anyio
async def test_a_tampered_token_is_refused() -> None:
    key = make_key()
    handler = _handler(key)
    header, payload, signature = mint(key).split(".")
    tampered = f"{header}.{payload}.{signature[:-4]}AAAA"

    with pytest.raises(InvalidAccessTokenError):
        _ = await handler.get_user_badge_from(tampered)


@pytest.mark.anyio
async def test_a_malformed_token_is_refused() -> None:
    key = make_key()
    handler = _handler(key)

    with pytest.raises(InvalidAccessTokenError):
        _ = await handler.get_user_badge_from("not-a-token")


def test_the_none_algorithm_is_refused_in_the_allow_list() -> None:
    key = make_key()
    with pytest.raises(InvalidArgumentError):
        _ = _handler(key, algorithms=("none",))


def test_a_symmetric_algorithm_is_refused_in_the_allow_list() -> None:
    key = make_key()
    with pytest.raises(InvalidArgumentError):
        _ = _handler(key, algorithms=("HS256",))


def test_an_empty_algorithm_allow_list_is_refused() -> None:
    key = make_key()
    with pytest.raises(InvalidArgumentError):
        _ = _handler(key, algorithms=())


def test_no_trusted_issuer_is_refused() -> None:
    key = make_key()
    with pytest.raises(InvalidArgumentError):
        _ = OidcTokenHandler(
            _provider_for(key),
            issuers=(),
            audience=AUDIENCE,
            clock=lambda: NOW,
        )


@pytest.mark.anyio
async def test_the_at_jwt_type_is_enforced_when_asked() -> None:
    key = make_key()
    handler = _handler(key, enforce_at_jwt_type=True)
    token = mint(key, typ="JWT")

    with pytest.raises(InvalidAccessTokenError):
        _ = await handler.get_user_badge_from(token)


@pytest.mark.anyio
async def test_the_at_jwt_type_is_accepted_when_present() -> None:
    key = make_key()
    handler = _handler(key, enforce_at_jwt_type=True)
    token = mint(key, typ="at+jwt")

    badge = await handler.get_user_badge_from(token)

    assert badge.get_user_identifier() == "alice"


@pytest.mark.anyio
async def test_a_missing_identifier_claim_is_refused() -> None:
    key = make_key()
    handler = _handler(key, claim="email")
    token = mint(key)

    with pytest.raises(InvalidAccessTokenError):
        _ = await handler.get_user_badge_from(token)


@pytest.mark.anyio
async def test_a_non_string_identifier_claim_is_refused() -> None:
    key = make_key()
    handler = _handler(key, claim="uid")
    token = mint(key, extra={"uid": 123})

    with pytest.raises(InvalidAccessTokenError):
        _ = await handler.get_user_badge_from(token)


@pytest.mark.anyio
async def test_the_iss_claim_can_be_the_identity_and_is_still_validated() -> None:
    key = make_key()
    handler = _handler(key, claim="iss")
    token = mint(key)

    badge = await handler.get_user_badge_from(token)

    assert badge.get_user_identifier() == ISSUER


@pytest.mark.anyio
async def test_the_issuer_allow_list_still_holds_when_the_identity_claim_is_iss() -> None:
    key = make_key()
    handler = _handler(key, claim="iss")
    token = mint(key, issuer="https://evil.example")

    with pytest.raises(InvalidAccessTokenError):
        _ = await handler.get_user_badge_from(token)


@pytest.mark.anyio
async def test_without_a_provider_the_claims_become_an_oidc_user() -> None:
    key = make_key()
    handler = _handler(key)
    token = mint(key, extra={"name": "Alice"})

    badge = await handler.get_user_badge_from(token)
    user = await badge.get_user()

    assert isinstance(user, OidcUser)
    assert user.claims["name"] == "Alice"


@pytest.mark.anyio
async def test_a_plain_provider_loads_the_user_by_identifier() -> None:
    key = make_key()

    @final
    class _Plain(UserProviderInterface):
        @override
        async def load_user_by_identifier(self, identifier: str) -> UserInterface:
            return InMemoryUser(identifier, roles=["ROLE_STAFF"])

        @override
        def supports_class(self, user_class: type) -> bool:
            del user_class
            return True

    handler = _handler(key, user_provider=_Plain())
    badge = await handler.get_user_badge_from(mint(key))
    user = await badge.get_user()

    assert isinstance(user, InMemoryUser)
    assert list(user.get_roles()) == ["ROLE_STAFF"]


@pytest.mark.anyio
async def test_an_attributes_based_provider_receives_the_claims() -> None:
    key = make_key()
    seen: dict[str, object] = {}

    @final
    class _Attributed(AttributesBasedUserProviderInterface):
        @override
        async def load_user_by_identifier(
            self,
            identifier: str,
            attributes: Mapping[str, object] | None = None,
        ) -> UserInterface:
            seen.update(attributes or {})
            return InMemoryUser(identifier, roles=["ROLE_USER"])

        @override
        def supports_class(self, user_class: type) -> bool:
            del user_class
            return True

    handler = _handler(key, user_provider=_Attributed())
    token = mint(key, extra={"department": "sales"})
    badge = await handler.get_user_badge_from(token)
    _ = await badge.get_user()

    assert seen["department"] == "sales"


@pytest.mark.anyio
async def test_an_unknown_kid_triggers_one_refetch_then_verifies() -> None:
    old = make_key("old")
    rotated = make_key("new")

    @final
    class _Rotating(OidcKeySetProviderInterface):
        calls: int

        def __init__(self) -> None:
            self.calls = 0

        @override
        async def get_key_set(self, *, force_refresh: bool = False) -> KeySet:
            self.calls += 1
            return make_key_set(rotated) if force_refresh else make_key_set(old)

    provider = _Rotating()
    handler = OidcTokenHandler(
        provider,
        issuers=(ISSUER,),
        audience=AUDIENCE,
        clock=lambda: NOW,
    )
    token = mint(rotated)

    badge = await handler.get_user_badge_from(token)

    assert badge.get_user_identifier() == "alice"
    assert provider.calls == 2


@pytest.mark.anyio
async def test_an_unknown_kid_that_stays_unknown_is_refused() -> None:
    old = make_key("old")
    signer = make_key("ghost")

    @final
    class _Stubborn(OidcKeySetProviderInterface):
        @override
        async def get_key_set(self, *, force_refresh: bool = False) -> KeySet:
            del force_refresh
            return make_key_set(old)

    handler = OidcTokenHandler(
        _Stubborn(),
        issuers=(ISSUER,),
        audience=AUDIENCE,
        clock=lambda: NOW,
    )

    with pytest.raises(InvalidAccessTokenError):
        _ = await handler.get_user_badge_from(mint(signer))
