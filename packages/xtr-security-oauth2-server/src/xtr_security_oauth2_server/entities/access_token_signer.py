"""Everything signing an access token needs, gathered into one value."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from typing_extensions import override

if TYPE_CHECKING:
    from xtr_clock import ClockInterface
    from xtr_security_jwt.services.jws_provider import JwsProviderInterface

__all__ = ["AccessTokenSigner"]


@final
@dataclass(frozen=True, repr=False, slots=True)
class AccessTokenSigner:
    """The key, the names and the clock an access token signs itself with.

    An access token is handed one of these and then knows how to produce the
    JWT a resource server reads. Five things decide what that token says, and
    they travel together because none of them is useful without the rest: a
    provider holding the signing key, the id that key is published under, the
    issuer to claim, the audience to address, and the clock the issue and
    not-before instants are read from.

    They are one value rather than five arguments because every grant that
    issues a token passes the same set unchanged, and because a token signed
    with the key of one deployment and the issuer of another is a token no
    resource server should accept — keeping them together means that mismatch
    cannot be assembled a piece at a time.

    Attributes:
        jws_provider: Signs the claims, holding the key and the algorithm.
        key_id: The id the signing key is published under, stamped as ``kid``
            so a reader of the published key set knows which key to try.
        issuer: The origin the token claims to come from.
        clock: Where the issue and not-before instants are read from.
        audience: Who the token is addressed to, or ``None`` to address the
            client it was issued to.
    """

    jws_provider: JwsProviderInterface
    key_id: str
    issuer: str
    clock: ClockInterface
    audience: str | None = None

    @override
    def __repr__(self) -> str:
        """Name what it signs for, and the provider by type alone.

        The provider holds the signing key. Printing it would hand whatever
        reading it chooses to a log line or a traceback, so only its type is
        named here — enough to tell which provider is wired, nothing of what
        it holds.
        """
        return (
            f"{type(self).__name__}(jws_provider={type(self.jws_provider).__name__}, "
            f"key_id={self.key_id!r}, issuer={self.issuer!r}, audience={self.audience!r})"
        )
