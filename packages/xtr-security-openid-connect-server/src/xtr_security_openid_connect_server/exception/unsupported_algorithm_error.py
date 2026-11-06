"""A token hash was asked for under a signature algorithm that names no digest."""

from __future__ import annotations

from typing import final

from .open_id_connect_server_error import OpenIdConnectServerError

__all__ = ["UnsupportedAlgorithmError"]


@final
class UnsupportedAlgorithmError(OpenIdConnectServerError):
    """No token hash can be taken for a signature algorithm.

    A token hash is the left half of the digest the ID token's algorithm signs
    with, so a client recomputes it from the ``alg`` header alone. An algorithm
    whose digest cannot be told from its name leaves nothing to recompute it
    with; guessing one would hand out ID tokens every client rejects, so the
    algorithm is refused here instead, by name, where the deployment that
    chose it sees it.

    Attributes:
        algorithm: The signature algorithm no token hash could be taken for.
    """

    __slots__ = ("algorithm",)

    def __init__(self, algorithm: str) -> None:
        """Report that ``algorithm`` names no digest a token hash is taken with."""
        super().__init__(
            f'No token hash can be taken for the signature algorithm "{algorithm}": a token '
            "hash is half of the digest the algorithm signs with, and only a name ending in "
            "256, 384 or 512, or EdDSA, says which digest that is.",
        )
        self.algorithm = algorithm
