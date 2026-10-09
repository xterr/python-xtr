"""The published JWK set and the id the signing key is published under."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from joserfc.jwk import RSAKey
from xtr_security_core.exception import InvalidArgumentError

from tests.support.keys import (
    EC_PRIVATE_PEM,
    HMAC_SECRET,
    RSA_PRIVATE_PEM,
    RSA_PUBLIC_PEM,
    SECOND_RSA_PUBLIC_JWKS,
    SECOND_RSA_PUBLIC_PEM,
)
from xtr_security_jwt.services.key_loader.public_key_set import public_key_set, signing_key_id
from xtr_security_jwt.services.key_loader.raw_key_loader import RawKeyLoader

if TYPE_CHECKING:
    from pathlib import Path

#: Every member of an RSA JWK that only a holder of the signing key may know.
_PRIVATE_RSA_MEMBERS = frozenset({"d", "p", "q", "dp", "dq", "qi"})


def _loader_with_extras(directory: Path, *materials: str) -> RawKeyLoader:
    """Return a loader trusting one extra public key per material, each in its own file."""
    paths: list[str] = []
    for index, material in enumerate(materials):
        suffix = ".jwks.json" if material.lstrip().startswith("{") else ".pem"
        file = directory / f"extra-{index}{suffix}"
        _ = file.write_text(material, encoding="utf-8")
        paths.append(str(file))
    return RawKeyLoader(RSA_PRIVATE_PEM, None, None, tuple(paths))


def test_it_publishes_the_signing_key_as_a_jwk_set() -> None:
    loader = RawKeyLoader(RSA_PRIVATE_PEM, None)

    document = public_key_set(loader, "RS256")

    assert [key["kty"] for key in document["keys"]] == ["RSA"]


def test_a_published_key_carries_its_public_members_alone() -> None:
    loader = RawKeyLoader(RSA_PRIVATE_PEM, None)

    document = public_key_set(loader, "RS256")

    assert set(document["keys"][0]) == {"kty", "kid", "n", "e"}


def test_a_published_key_names_itself_by_its_rfc_7638_thumbprint() -> None:
    loader = RawKeyLoader(RSA_PRIVATE_PEM, None)

    document = public_key_set(loader, "RS256")

    assert document["keys"][0]["kid"] == RSAKey.import_key(RSA_PUBLIC_PEM).thumbprint()


def test_it_publishes_every_additional_public_key(tmp_path: Path) -> None:
    loader = _loader_with_extras(tmp_path, SECOND_RSA_PUBLIC_PEM)

    document = public_key_set(loader, "RS256")

    assert [key["kid"] for key in document["keys"]] == [
        RSAKey.import_key(RSA_PUBLIC_PEM).thumbprint(),
        RSAKey.import_key(SECOND_RSA_PUBLIC_PEM).thumbprint(),
    ]


def test_an_additional_key_carrying_its_own_id_keeps_it(tmp_path: Path) -> None:
    loader = _loader_with_extras(tmp_path, SECOND_RSA_PUBLIC_JWKS)

    document = public_key_set(loader, "RS256")

    assert [key["kid"] for key in document["keys"][1:]] == ["rsa-2"]


def test_no_published_key_leaks_a_private_member(tmp_path: Path) -> None:
    loader = _loader_with_extras(tmp_path, SECOND_RSA_PUBLIC_JWKS)

    document = public_key_set(loader, "RS256")

    assert [key for key in document["keys"] if _PRIVATE_RSA_MEMBERS & set(key)] == []


def test_a_shared_secret_is_never_published() -> None:
    loader = RawKeyLoader(HMAC_SECRET, None)

    with pytest.raises(InvalidArgumentError, match="HS256"):
        _ = public_key_set(loader, "HS256")


def test_key_material_that_cannot_be_read_is_refused() -> None:
    loader = RawKeyLoader("-----BEGIN PUBLIC KEY-----\nnot a key\n", None)

    with pytest.raises(InvalidArgumentError):
        _ = public_key_set(loader, "RS256")


def test_a_key_of_another_type_than_the_algorithm_needs_is_refused() -> None:
    loader = RawKeyLoader(EC_PRIVATE_PEM, None)

    with pytest.raises(InvalidArgumentError):
        _ = public_key_set(loader, "RS256")


def test_the_signing_key_is_named_by_its_rfc_7638_thumbprint() -> None:
    loader = RawKeyLoader(RSA_PRIVATE_PEM, None)

    assert signing_key_id(loader, "RS256") == RSAKey.import_key(RSA_PUBLIC_PEM).thumbprint()


def test_a_loader_that_only_verifies_names_its_key_the_same_way() -> None:
    loader = RawKeyLoader(None, RSA_PUBLIC_PEM)

    assert signing_key_id(loader, "RS256") == RSAKey.import_key(RSA_PUBLIC_PEM).thumbprint()


def test_the_signing_key_id_names_a_key_the_published_set_holds(tmp_path: Path) -> None:
    loader = _loader_with_extras(tmp_path, SECOND_RSA_PUBLIC_JWKS)

    published = [key["kid"] for key in public_key_set(loader, "RS256")["keys"]]

    assert signing_key_id(loader, "RS256") in published


def test_a_shared_secret_is_never_named() -> None:
    loader = RawKeyLoader(HMAC_SECRET, None)

    with pytest.raises(InvalidArgumentError, match="HS256"):
        _ = signing_key_id(loader, "HS256")
