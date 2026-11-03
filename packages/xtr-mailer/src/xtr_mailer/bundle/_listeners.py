"""The listeners the bundle registers on the event dispatcher, each at its ``PRIORITY``.

Every email a transport sends is announced on the dispatcher, and these listeners change it on
the way: the configured headers first, then the S/MIME signature and encryption, then the DKIM
signature, and last the configured envelope. In debug mode, a listener records every email.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from xtr_dependency_injection import (
    ContainerBuilder,
    Definition,
    Reference,
    ServiceConfigurator,
    bundle_active,
)

from xtr_mailer.event import MessageEvent
from xtr_mailer.event_listener import (
    DkimSignedMessageListener,
    EnvelopeListener,
    InMemorySmimeCertificateRepository,
    MessageListener,
    MessageLoggerListener,
    MessengerTransportListener,
    SmimeEncryptedMessageListener,
    SmimeSignedMessageListener,
)
from xtr_mailer.exception import LogicError

from ._crypto_listeners import (
    dkim_signed_message_listener,
    in_memory_smime_certificate_repository,
    smime_encrypted_message_listener,
    smime_signed_message_listener,
)
from ._services import envelope_listener, message_listener, message_logger_listener

if TYPE_CHECKING:
    from .mailer_config import MailerConfig
    from .smime_encrypter_config import SmimeEncrypterConfig

__all__ = ["register_listeners"]

_REPOSITORY: Final = "mailer.smime_certificates"
"""The qualifier of the repository holding the configured S/MIME certificates."""

_Listener = (
    DkimSignedMessageListener
    | EnvelopeListener
    | MessageListener
    | MessageLoggerListener
    | MessengerTransportListener
    | SmimeEncryptedMessageListener
    | SmimeSignedMessageListener
)


def register_listeners(
    config: MailerConfig, services: ServiceConfigurator, builder: ContainerBuilder
) -> None:
    """Register the listener of each configured option, and the recorder in debug mode.

    Raises:
        LogicError: An option needs a listener and the event dispatcher bundle is inactive.
    """
    options = _configured_options(config)
    if not bundle_active(builder, "event_dispatcher"):
        if options:
            raise LogicError(
                f'The "{options[0]}" option needs the "event_dispatcher" bundle; install '
                "xtr-event-dispatcher beside xtr-mailer."
            )
        return
    from xtr_event_dispatcher.bundle import LISTENER_TAG  # noqa: PLC0415 -- optional peer

    for definition, listener in [*_recorders(services, builder), *_options(config, services)]:
        _ = definition.add_tag(
            LISTENER_TAG, event=MessageEvent, method="on_message", priority=listener.PRIORITY
        )


def _recorders(
    services: ServiceConfigurator, builder: ContainerBuilder
) -> list[tuple[Definition, type[_Listener]]]:
    """Register the listener recording every email in debug mode, and the bus's own."""
    listeners: list[tuple[Definition, type[_Listener]]] = []
    if builder.get_parameter("kernel.debug"):
        listeners.append((services.set(message_logger_listener), MessageLoggerListener))
    if bundle_active(builder, "messenger"):
        listeners.append((services.set(MessengerTransportListener), MessengerTransportListener))
    return listeners


def _options(
    config: MailerConfig, services: ServiceConfigurator
) -> list[tuple[Definition, type[_Listener]]]:
    """Register the listener of each configured option."""
    listeners: list[tuple[Definition, type[_Listener]]] = []
    if config.envelope.is_configured():
        envelope = services.set(envelope_listener).set_argument("envelope", config.envelope)
        listeners.append((envelope, EnvelopeListener))
    if config.headers or config.tracking.is_configured():
        headers = services.set(message_listener).set_arguments(
            {"headers": dict(config.headers), "tracking": config.tracking}
        )
        listeners.append((headers, MessageListener))
    if config.dkim_signer is not None:
        dkim = services.set(dkim_signed_message_listener)
        signer = dkim.set_argument("signer", config.dkim_signer)
        listeners.append((signer, DkimSignedMessageListener))
    if config.smime_signer is not None:
        smime = services.set(smime_signed_message_listener)
        signer = smime.set_argument("signer", config.smime_signer)
        listeners.append((signer, SmimeSignedMessageListener))
    if config.smime_encrypter is not None:
        encrypter = _encrypter(config.smime_encrypter, services)
        listeners.append((encrypter, SmimeEncryptedMessageListener))
    return listeners


def _configured_options(config: MailerConfig) -> list[str]:
    """Return the name of every configured option a listener carries out."""
    configured = {
        "envelope": config.envelope.is_configured(),
        "headers": bool(config.headers),
        "tracking": config.tracking.is_configured(),
        "dkim_signer": config.dkim_signer is not None,
        "smime_signer": config.smime_signer is not None,
        "smime_encrypter": config.smime_encrypter is not None,
    }
    return [option for option, given in configured.items() if given]


def _encrypter(encrypter: SmimeEncrypterConfig, services: ServiceConfigurator) -> Definition:
    """Register the encrypting listener over its repository, holding the certificates given."""
    repository = encrypter.repository
    if repository is None:
        holder = services.set(in_memory_smime_certificate_repository, qualifier=_REPOSITORY)
        _ = holder.set_argument("certificates", dict(encrypter.certificates))
        repository = Reference(InMemorySmimeCertificateRepository, _REPOSITORY)
    return services.set(smime_encrypted_message_listener(repository)).set_argument(
        "encrypter", encrypter
    )
