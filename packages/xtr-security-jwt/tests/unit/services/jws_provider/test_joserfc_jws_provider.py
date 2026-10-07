"""The joserfc JWS provider signs, verifies, and judges times as the reference does."""

from __future__ import annotations

import json
import secrets
from typing import TYPE_CHECKING, final

import pytest
from joserfc.jwk import ECKey, KeySet, OctKey
from typing_extensions import override
from xtr_clock import MockClock
from xtr_security.bundle import InvalidConfigurationError
from xtr_security_core.exception import InvalidArgumentError

from tests.support.keys import (
    EC_PUBLIC_PEM,
    HMAC_SECRET,
    RSA_PRIVATE_PEM,
    RSA_PUBLIC_PEM,
    SECOND_RSA_PRIVATE_PEM,
    SECOND_RSA_PUBLIC_JWKS,
    SECOND_RSA_PUBLIC_PEM,
)
from xtr_security_jwt.services.jws_provider.joserfc_jws_provider import (
    JoserfcJwsProvider,
    require_hmac_secret_length,
)
from xtr_security_jwt.services.jws_provider.jws_provider_interface import JwsProviderInterface
from xtr_security_jwt.services.key_loader.additional_public_key import AdditionalPublicKey
from xtr_security_jwt.services.key_loader.key_loader_interface import KeyLoaderInterface
from xtr_security_jwt.services.key_loader.raw_key_loader import RawKeyLoader

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from joserfc.jwk import Key


def _clock() -> MockClock:
    return MockClock("2024-01-01 00:00:00")


def _provider(**kwargs: object) -> JoserfcJwsProvider:
    loader = RawKeyLoader(RSA_PRIVATE_PEM, None)
    ttl = kwargs.get("ttl", 3600)
    skew = kwargs.get("clock_skew", 0)
    allow = kwargs.get("allow_no_expiration", False)
    return JoserfcJwsProvider(
        loader,
        "RS256",
        ttl if isinstance(ttl, int) else 3600,
        skew if isinstance(skew, int) else 0,
        _clock(),
        allow_no_expiration=bool(allow),
    )


def _token_from_the_second_key(kid: str | None = None) -> str:
    """Mint a token signed by the second key, naming ``kid`` in its header."""
    other = JoserfcJwsProvider(
        RawKeyLoader(SECOND_RSA_PRIVATE_PEM, None),
        "RS256",
        3600,
        0,
        _clock(),
    )
    header = {"kid": kid} if kid is not None else None
    return other.create({"sub": "ada"}, header).get_token()


def _attempted_keys(monkeypatch: pytest.MonkeyPatch) -> list[Key]:
    """Record every key a provider really tries, leaving the verify itself alone."""
    tried: list[Key] = []
    verifies = JoserfcJwsProvider._verifies_with

    def record(self: JoserfcJwsProvider, token: str, key: Key) -> bool:
        tried.append(key)
        return verifies(self, token, key)

    monkeypatch.setattr(JoserfcJwsProvider, "_verifies_with", record)
    return tried


def test_it_implements_the_provider_interface() -> None:
    assert isinstance(_provider(), JwsProviderInterface)


def test_it_signs_and_the_token_is_signed() -> None:
    created = _provider().create({"sub": "ada"})

    assert created.is_signed() is True
    assert created.get_token().count(".") == 2


def test_it_stamps_iat_and_exp_from_the_ttl() -> None:
    now = int(_clock().now().timestamp())
    token = _provider(ttl=100).create({"sub": "ada"}).get_token()
    loaded = _provider(ttl=100).load(token)

    assert loaded.get_payload()["iat"] == now
    assert loaded.get_payload()["exp"] == now + 100


def test_it_keeps_a_payload_iat_and_exp() -> None:
    token = _provider().create({"sub": "ada", "iat": 10, "exp": 20}).get_token()
    loaded = _provider().load(token)

    assert loaded.get_payload()["iat"] == 10
    assert loaded.get_payload()["exp"] == 20


def test_a_round_trip_verifies() -> None:
    token = _provider().create({"sub": "ada"}).get_token()
    loaded = _provider().load(token)

    assert loaded.is_verified() is True
    assert loaded.get_payload()["sub"] == "ada"


def test_a_tampered_token_does_not_verify() -> None:
    token = _provider().create({"sub": "ada"}).get_token()
    loaded = _provider().load(token[:-3] + "aaa")

    assert loaded.is_verified() is False


def test_a_token_from_another_key_does_not_verify() -> None:
    loaded = _provider().load(_token_from_the_second_key())

    assert loaded.is_verified() is False


def test_an_additional_public_key_verifies_a_rotated_token(tmp_path: Path) -> None:
    extra = tmp_path / "old.pem"
    _ = extra.write_text(SECOND_RSA_PUBLIC_PEM, encoding="utf-8")
    loader = RawKeyLoader(RSA_PRIVATE_PEM, RSA_PUBLIC_PEM, None, (str(extra),))
    provider = JoserfcJwsProvider(loader, "RS256", 3600, 0, _clock())

    assert provider.load(_token_from_the_second_key()).is_verified() is True


def test_a_malformed_token_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = _provider().load("not-a-token")


def test_it_refuses_an_unsupported_algorithm() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = JoserfcJwsProvider(RawKeyLoader(RSA_PRIVATE_PEM, None), "none", 3600, 0, _clock())


def test_it_signs_and_verifies_with_a_shared_secret() -> None:
    loader = RawKeyLoader(HMAC_SECRET, None)
    provider = JoserfcJwsProvider(loader, "HS256", 3600, 0, _clock())
    token = provider.create({"sub": "ada"}).get_token()

    assert provider.load(token).is_verified() is True


def test_no_ttl_and_no_exp_mints_a_token_without_expiry() -> None:
    provider = JoserfcJwsProvider(
        RawKeyLoader(RSA_PRIVATE_PEM, None),
        "RS256",
        None,
        0,
        _clock(),
        allow_no_expiration=True,
    )
    token = provider.create({"sub": "ada"}).get_token()
    loaded = provider.load(token)

    assert "exp" not in loaded.get_payload()
    assert loaded.is_invalid() is False


def test_a_short_hs256_secret_is_refused_naming_the_floor() -> None:
    with pytest.raises(InvalidConfigurationError) as info:
        require_hmac_secret_length("HS256", "short")

    message = str(info.value)
    assert "HS256" in message
    assert "32 bytes" in message


def test_a_48_byte_secret_is_refused_for_hs512() -> None:
    with pytest.raises(InvalidConfigurationError, match="64 bytes"):
        require_hmac_secret_length("HS512", "a" * 48)


def test_a_32_byte_secret_is_accepted_for_hs256() -> None:
    require_hmac_secret_length("HS256", "a" * 32)


def test_a_non_hmac_algorithm_has_no_secret_floor() -> None:
    require_hmac_secret_length("RS256", "short")


@final
class _CountingKeyLoader(KeyLoaderInterface):
    """A key loader that answers like the raw one and counts what it was asked for."""

    def __init__(self, signing_key: str) -> None:
        self._loader = RawKeyLoader(signing_key, None)
        self.key_calls = 0
        self.additional_calls = 0

    @override
    def load_key(self, key_type: str) -> str:
        self.key_calls += 1
        return self._loader.load_key(key_type)

    @override
    def get_passphrase(self) -> str | None:
        return self._loader.get_passphrase()

    @override
    def get_signing_key(self) -> str | None:
        return self._loader.get_signing_key()

    @override
    def get_public_key(self) -> str | None:
        return self._loader.get_public_key()

    @override
    def get_key_id(self) -> str | None:
        return self._loader.get_key_id()

    @override
    def get_additional_public_keys(self) -> Sequence[AdditionalPublicKey]:
        self.additional_calls += 1
        return self._loader.get_additional_public_keys()


def test_the_verifying_keys_are_imported_once_across_two_verifies() -> None:
    loader = _CountingKeyLoader(RSA_PRIVATE_PEM)
    provider = JoserfcJwsProvider(loader, "RS256", 3600, 0, _clock())
    token = provider.create({"sub": "ada"}).get_token()
    signing_calls = loader.key_calls

    first = provider.load(token)
    second = provider.load(token)

    assert (first.is_verified(), second.is_verified()) == (True, True)
    assert loader.key_calls == signing_calls + 1
    assert loader.additional_calls == 1


def test_a_token_whose_kid_names_an_extra_pem_verifies_in_one_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # ``jwt:generate-keypair`` writes ``<kid>.pem``, so the file's name is the id
    # a token's ``kid`` header names that key by.
    extra = tmp_path / "k2.pem"
    _ = extra.write_text(SECOND_RSA_PUBLIC_PEM, encoding="utf-8")
    loader = RawKeyLoader(RSA_PRIVATE_PEM, RSA_PUBLIC_PEM, None, (str(extra),))
    provider = JoserfcJwsProvider(loader, "RS256", 3600, 0, _clock())
    attempted = _attempted_keys(monkeypatch)

    loaded = provider.load(_token_from_the_second_key("k2"))

    assert loaded.is_verified() is True
    assert len(attempted) == 1


def test_a_token_whose_kid_names_a_key_in_a_jwks_extra_verifies_in_one_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A JWK set carries each key's own ``kid``, and that id wins over the name of
    # the file the set was read from.
    extra = tmp_path / "published.jwks.json"
    _ = extra.write_text(SECOND_RSA_PUBLIC_JWKS, encoding="utf-8")
    loader = RawKeyLoader(RSA_PRIVATE_PEM, RSA_PUBLIC_PEM, None, (str(extra),))
    provider = JoserfcJwsProvider(loader, "RS256", 3600, 0, _clock())
    attempted = _attempted_keys(monkeypatch)

    loaded = provider.load(_token_from_the_second_key("rsa-2"))

    assert loaded.is_verified() is True
    assert len(attempted) == 1


def test_a_token_naming_no_kid_is_still_tried_against_every_trusted_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extra = tmp_path / "k2.pem"
    _ = extra.write_text(SECOND_RSA_PUBLIC_PEM, encoding="utf-8")
    loader = RawKeyLoader(RSA_PRIVATE_PEM, RSA_PUBLIC_PEM, None, (str(extra),))
    provider = JoserfcJwsProvider(loader, "RS256", 3600, 0, _clock())
    attempted = _attempted_keys(monkeypatch)

    loaded = provider.load(_token_from_the_second_key())

    assert loaded.is_verified() is True
    assert len(attempted) == 2


def test_an_additional_public_key_that_cannot_be_read_is_refused(tmp_path: Path) -> None:
    extra = tmp_path / "broken.pem"
    _ = extra.write_text("not a key at all", encoding="utf-8")
    loader = RawKeyLoader(RSA_PRIVATE_PEM, RSA_PUBLIC_PEM, None, (str(extra),))
    provider = JoserfcJwsProvider(loader, "RS256", 3600, 0, _clock())
    token = provider.create({"sub": "ada"}).get_token()

    with pytest.raises(InvalidArgumentError, match="broken"):
        _ = provider.load(token)


def test_a_jwks_extra_holding_no_key_of_the_algorithms_type_is_refused(tmp_path: Path) -> None:
    extra = tmp_path / "wrong.jwks.json"
    elliptic = json.dumps(KeySet([ECKey.import_key(EC_PUBLIC_PEM)]).as_dict(private=False))
    _ = extra.write_text(elliptic, encoding="utf-8")
    loader = RawKeyLoader(RSA_PRIVATE_PEM, RSA_PUBLIC_PEM, None, (str(extra),))
    provider = JoserfcJwsProvider(loader, "RS256", 3600, 0, _clock())
    token = provider.create({"sub": "ada"}).get_token()

    with pytest.raises(InvalidArgumentError, match="RSA"):
        _ = provider.load(token)


def _oct_jwk(key_id: str, secret: str) -> dict[str, object]:
    """Return the JWK a shared ``secret`` is published as, carrying ``key_id``."""
    return dict(OctKey.import_key(secret, parameters={"kid": key_id}).as_dict())


#: A shared secret of sixteen bytes — above joserfc's own floor, below every HMAC one.
_SHORT_SECRET: str = secrets.token_hex(8)


def test_a_short_shared_secret_in_a_jwks_extra_is_refused_naming_the_key(tmp_path: Path) -> None:
    # A secret handed in as a JWK set must clear the same floor as one handed in
    # as text: a 16-byte HS256 key would verify a token anyone can forge.
    extra = tmp_path / "published.jwks.json"
    jwk = _oct_jwk("hs-short", _SHORT_SECRET)
    _ = extra.write_text(json.dumps({"keys": [jwk]}), encoding="utf-8")
    loader = RawKeyLoader(HMAC_SECRET, None, None, (str(extra),))
    provider = JoserfcJwsProvider(loader, "HS256", 3600, 0, _clock())
    token = provider.create({"sub": "ada"}).get_token()

    with pytest.raises(InvalidConfigurationError) as info:
        _ = provider.load(token)

    message = str(info.value)
    assert "published" in message
    assert "HS256" in message
    assert "32 bytes" in message


def test_a_short_shared_secret_in_a_lone_jwk_extra_is_refused(tmp_path: Path) -> None:
    extra = tmp_path / "old.jwks.json"
    _ = extra.write_text(json.dumps(_oct_jwk("hs-short", _SHORT_SECRET)), encoding="utf-8")
    loader = RawKeyLoader(HMAC_SECRET, None, None, (str(extra),))
    provider = JoserfcJwsProvider(loader, "HS256", 3600, 0, _clock())
    token = provider.create({"sub": "ada"}).get_token()

    with pytest.raises(InvalidConfigurationError, match="32 bytes"):
        _ = provider.load(token)


def test_a_long_enough_shared_secret_in_a_jwks_extra_verifies_a_rotated_token(
    tmp_path: Path,
) -> None:
    rotated = secrets.token_hex(16)
    extra = tmp_path / "rotated.jwks.json"
    _ = extra.write_text(
        json.dumps({"keys": [_oct_jwk("hs-rotated", rotated)]}),
        encoding="utf-8",
    )
    other = JoserfcJwsProvider(RawKeyLoader(rotated, None), "HS256", 3600, 0, _clock())
    loader = RawKeyLoader(HMAC_SECRET, None, None, (str(extra),))
    provider = JoserfcJwsProvider(loader, "HS256", 3600, 0, _clock())

    assert provider.load(other.create({"sub": "ada"}).get_token()).is_verified() is True
