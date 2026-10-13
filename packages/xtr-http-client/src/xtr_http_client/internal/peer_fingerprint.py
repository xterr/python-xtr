"""The digests a peer's certificate has to match, keyed by algorithm."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Final, cast

from xtr_http_client.exception import InvalidArgumentError
from xtr_http_client.internal.debug_type import debug_type

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["normalize_peer_fingerprint"]

_BY_LENGTH: Final = {32: "md5", 40: "sha1", 64: "sha256"}
"""How long a hex digest of each algorithm is, which is what names it."""

_PIN: Final = "pin-sha256"
_PIN_LENGTH: Final = 44
"""The length of a base64 pin, which is the one that is not hex."""


def normalize_peer_fingerprint(fingerprint: object) -> dict[str, str | tuple[str, ...]]:
    """Read a fingerprint into digests keyed by the algorithm that made them.

    A lone digest names its own algorithm: each produces a different length,
    and the one that is not hex is a base64 pin. That is why a caller can pin
    a certificate by pasting a digest without saying what it is — and why one
    of a length no algorithm has is refused rather than guessed at.

    The colons a digest is usually written with are dropped, because that is
    how a tool prints it and not part of it. A pin is always a list, since
    more than one may be accepted — which is what makes rotating a
    certificate possible without a window where nothing matches.

    Raises:
        InvalidArgumentError: When a lone digest is of a length no algorithm
            produces, or the fingerprint is neither a digest nor a mapping.
    """
    if isinstance(fingerprint, str):
        return _detected(fingerprint.replace(":", ""))
    if isinstance(fingerprint, Mapping):
        # Typed by `RequestOptions` as digests keyed by algorithm; the cast says
        # so once rather than at every lookup below.
        named = cast("Mapping[str, str | Sequence[str]]", fingerprint)
        return {algorithm: _digests(algorithm, value) for algorithm, value in named.items()}

    raise InvalidArgumentError(
        f'Option "peer_fingerprint" must be a string or a mapping, '
        f'"{debug_type(fingerprint)}" given.'
    )


def _detected(digest: str) -> dict[str, str | tuple[str, ...]]:
    if len(digest) == _PIN_LENGTH:
        return {_PIN: (digest,)}

    algorithm = _BY_LENGTH.get(len(digest))
    if algorithm is None:
        raise InvalidArgumentError(f'Cannot auto-detect fingerprint algorithm for "{digest}".')

    return {algorithm: digest}


def _digests(algorithm: str, value: str | Sequence[str]) -> str | tuple[str, ...]:
    if algorithm != _PIN:
        return value.replace(":", "") if isinstance(value, str) else value[0].replace(":", "")
    return (value,) if isinstance(value, str) else tuple(value)
