"""An encoder that also takes header parameters when it signs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from typing_extensions import override

from .jwt_encoder_interface import JwtEncoderInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["HeaderAwareJwtEncoderInterface"]


@runtime_checkable
class HeaderAwareJwtEncoderInterface(JwtEncoderInterface, Protocol):
    """A :class:`JwtEncoderInterface` whose ``encode`` also takes a header.

    An encoder built for it lets the token manager pass header parameters — the
    type, the key id — through to the signature. The token manager hands a header
    only to an encoder that declares this interface, and drops it silently for a
    plain one.
    """

    @override
    def encode(
        self,
        data: Mapping[str, object],
        header: Mapping[str, object] | None = None,
    ) -> str:
        """Sign ``data`` into a token, carrying the extra ``header`` parameters.

        Raises:
            JwtEncodeFailureError: When the token cannot be signed.
        """
        ...
