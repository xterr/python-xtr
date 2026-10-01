"""What signs a payload into a token and reads one back with its state."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_security_jwt.signature.created_jws import CreatedJws
    from xtr_security_jwt.signature.loaded_jws import LoadedJws

__all__ = ["JwsProviderInterface"]


@runtime_checkable
class JwsProviderInterface(Protocol):
    """Signs a payload into a compact token and reads one back for verification.

    A provider owns the keys and the algorithm: it stamps the registered time
    claims, signs, and reports whether a token it reads back verifies and how its
    times stand. It makes no judgement about the issuer, audience or subject —
    that belongs to whoever consumes the loaded payload.
    """

    def create(
        self,
        payload: Mapping[str, object],
        header: Mapping[str, object] | None = None,
    ) -> CreatedJws:
        """Sign ``payload`` into a token, with optional extra ``header`` parameters."""
        ...

    def load(self, token: str) -> LoadedJws:
        """Read ``token`` back, checking its signature and judging its times."""
        ...
