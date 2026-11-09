"""A token hash was asked for under a signature algorithm that names no digest."""

from __future__ import annotations

from typing import final

from .open_id_connect_server_error import OpenIdConnectServerError

__all__ = ["UnsupportedAlgorithmError"]


@final
class UnsupportedAlgorithmError(OpenIdConnectServerError):
    """No token hash can be taken for a signature algorithm.

    A token hash is the left half of the digest the ID token's algorithm signs
    with, so a client recomputes it from the ``alg`` header — and, for
    ``EdDSA``, the curve of the key it verified the token with. An algorithm
    or a curve whose digest cannot be told leaves nothing to recompute it
    with; guessing one would hand out ID tokens every client rejects, so it is
    refused here instead, by name, where the deployment that chose it sees it.

    Attributes:
        algorithm: The signature algorithm no token hash could be taken for.
        curve: The curve it was asked for over, or ``None`` when the algorithm
            names no digest whatever the curve.
    """

    __slots__ = ("algorithm", "curve")

    def __init__(self, algorithm: str, curve: str | None = None) -> None:
        """Report that ``algorithm``, over ``curve`` when one is named, names no digest."""
        if curve is None:
            reason = (
                f'No token hash can be taken for the signature algorithm "{algorithm}": a token '
                "hash is half of the digest the algorithm signs with, and only a name ending in "
                "256, 384 or 512, or EdDSA, says which digest that is."
            )
        else:
            reason = (
                f'No token hash can be taken for the signature algorithm "{algorithm}" over the '
                f'curve "{curve}": EdDSA signs with SHA-512 over Ed25519 and with SHAKE256 over '
                "Ed448, and no other curve says which digest that is."
            )
        super().__init__(reason)
        self.algorithm = algorithm
        self.curve = curve
