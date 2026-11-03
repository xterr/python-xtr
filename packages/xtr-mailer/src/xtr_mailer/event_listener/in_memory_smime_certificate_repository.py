"""S/MIME certificates found in a mapping of addresses to certificate paths."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, final

from typing_extensions import override

from .smime_certificate_repository_interface import SmimeCertificateRepositoryInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["InMemorySmimeCertificateRepository"]


@final
class InMemorySmimeCertificateRepository(SmimeCertificateRepositoryInterface):
    """Finds each address's certificate path in the mapping it was built with.

    An address is found as it is written in the mapping, letter case included:
    ``User@example.com`` is not ``user@example.com``.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_certificates",)

    def __init__(self, certificates: Mapping[str, str] | None = None) -> None:
        """Find certificates in a copy of ``certificates``: certificate paths by address."""
        self._certificates: dict[str, str] = dict(certificates or {})

    @override
    def find_certificate_path_for(self, email: str) -> str | None:
        """Return the certificate path mapped to ``email``; ``None`` when there is none."""
        return self._certificates.get(email)
