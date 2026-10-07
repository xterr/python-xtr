"""An extra public key a deployment trusts, with the id its source names it by."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

__all__ = ["AdditionalPublicKey"]


@final
@dataclass(frozen=True, slots=True)
class AdditionalPublicKey:
    """One extra public key a presented token may also be verified against.

    A key file is named after the key it holds — ``jwt:generate-keypair`` writes
    ``<kid>.pem`` and ``<kid>.jwks.json`` — so the name a loader read the
    material under is the id a token's ``kid`` header names that key by. Material
    carrying its own ``kid``, a JWK or a JWK set, names itself and wins over this.

    Attributes:
        key_id: The id the material's source names it by.
        material: The key text: a PEM, a JWK, or a JWK set.
    """

    key_id: str
    material: str
