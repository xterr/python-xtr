"""The listeners signing and encrypting every email, built from their configuration.

Each opens its key or reads its certificates when the first email reaches it, never at build or
boot: a key given through ``env()`` is checked where it is used.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Annotated

from xtr_dependency_injection import Reference, Target
from xtr_mime.crypto import DkimSigner, SMimeSigner

from xtr_mailer.event_listener import (
    DkimSignedMessageListener,
    InMemorySmimeCertificateRepository,
    SmimeCertificateRepositoryInterface,
    SmimeEncryptedMessageListener,
    SmimeSignedMessageListener,
)

from .dkim_signer_config import DkimSignerConfig
from .smime_encrypter_config import SmimeEncrypterConfig
from .smime_signer_config import SmimeSignerConfig

__all__ = [
    "dkim_signed_message_listener",
    "in_memory_smime_certificate_repository",
    "smime_encrypted_message_listener",
    "smime_signed_message_listener",
]


def dkim_signed_message_listener(signer: DkimSignerConfig) -> DkimSignedMessageListener:
    """Build the listener signing every email with the configured DKIM key."""
    return DkimSignedMessageListener(
        DkimSigner(
            signer.key,
            signer.domain,
            signer.select,
            default_options=signer.default_options(),
            passphrase=signer.passphrase,
        )
    )


def smime_signed_message_listener(signer: SmimeSignerConfig) -> SmimeSignedMessageListener:
    """Build the listener signing every email with the configured S/MIME certificate."""
    return SmimeSignedMessageListener(
        SMimeSigner(
            signer.certificate,
            signer.key,
            passphrase=signer.passphrase,
            extra_certificates=signer.extra_certificates,
        )
    )


def in_memory_smime_certificate_repository(
    certificates: Mapping[str, str],
) -> InMemorySmimeCertificateRepository:
    """Build the repository holding the configured certificates."""
    return InMemorySmimeCertificateRepository(certificates)


def smime_encrypted_message_listener(
    repository: Reference,
) -> Callable[..., SmimeEncryptedMessageListener]:
    """Return the factory of the encrypting listener over the ``repository`` service.

    The service is configuration, so its annotation is written onto the factory at runtime
    rather than in its signature.
    """

    def build(
        repository: SmimeCertificateRepositoryInterface, encrypter: SmimeEncrypterConfig
    ) -> SmimeEncryptedMessageListener:
        return SmimeEncryptedMessageListener(
            repository,
            encrypter.cipher,
            encrypter.on_missing_certificate,
            encrypter.encrypt_for_sender,
        )

    build.__name__ = "mailer_smime_encrypted_message_listener"
    build.__annotations__ = {
        "repository": _annotation(repository),
        "encrypter": SmimeEncrypterConfig,
        "return": SmimeEncryptedMessageListener,
    }
    return build


def _annotation(repository: Reference) -> object:
    """Return the annotation the container fills with the ``repository`` service."""
    if repository.qualifier is None:
        return repository.service
    qualifier = str(repository.qualifier)
    return Annotated[repository.service, Target(qualifier)]  # ty: ignore[invalid-type-form] -- the type is only known here, at runtime
