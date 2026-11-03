"""End-to-end over SMTP: signed and encrypted mail, capped transports, and the session closed."""

from __future__ import annotations

from typing import TYPE_CHECKING

import dkim
import pytest
from xtr_dependency_injection import Reference, env
from xtr_mime import Email
from xtr_rate_limiter import LimiterConfig, RateLimitExceededError
from xtr_rate_limiter.bundle import RateLimiterConfig

from tests.support.dkim_keys import SELECTOR, private_key_pem, published_key
from tests.support.mailer_kernel import Application, Provided, mailer_kernel
from tests.support.scripted_smtp_server import ScriptedSmtpServer
from tests.support.smime_checks import decrypt, verifies
from tests.support.smime_identities import authority, identity
from xtr_mailer import MailerInterface
from xtr_mailer.bundle import (
    DkimSignerConfig,
    MailerConfig,
    SmimeEncrypterConfig,
    SmimeSignerConfig,
    TransportConfig,
)
from xtr_mailer.event_listener import InMemorySmimeCertificateRepository

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio

_RECIPIENTS = ("r1@example.com", "hidden@example.com")


def _email(*, encrypt: bool = False) -> Email:
    email = (
        Email()
        .from_("sender@example.com")
        .to("r1@example.com")
        .bcc("hidden@example.com")
        .subject("Secret")
        .text("Line three")
    )
    if encrypt:
        _ = email.get_headers().add_text_header("X-SMime-Encrypt", "true")
    return email


async def _sent(server: ScriptedSmtpServer, application: Application, email: Email) -> bytes:
    async with await mailer_kernel(application).boot() as booted:
        await (await booted.container.get(MailerInterface)).send(email)
    [received] = server.messages
    return received


def _certificates(directory: Path) -> dict[str, str]:
    return {address: str(identity(address).write(directory, address)[0]) for address in _RECIPIENTS}


def _signer(directory: Path) -> SmimeSignerConfig:
    certificate, key = identity("sender@example.com").write(directory, "sign", "secret")
    return SmimeSignerConfig(str(certificate), str(key), passphrase="secret")


async def test_shutting_the_kernel_down_ends_the_smtp_session() -> None:
    async with ScriptedSmtpServer() as server:
        application = Application(mailer=MailerConfig(dsn=f"smtp://localhost:{server.port}"))
        _ = await _sent(server, application, _email())

    assert server.commands[-1] == "QUIT"


async def test_an_email_is_signed_with_the_dkim_key_from_the_environment() -> None:
    async with ScriptedSmtpServer() as server:
        signer = DkimSignerConfig(env("DKIM_KEY"), "example.com", SELECTOR)
        application = Application(
            mailer=MailerConfig(dsn=f"smtp://localhost:{server.port}", dkim_signer=signer),
            environ={"DKIM_KEY": private_key_pem()},
        )
        received = await _sent(server, application, _email())

    assert dkim.verify(received, dnsfunc=published_key)


async def test_without_the_dkim_key_the_kernel_still_boots() -> None:
    signer = DkimSignerConfig(env("DKIM_KEY"), "example.com", SELECTOR)
    application = Application(mailer=MailerConfig(dkim_signer=signer))

    async with await mailer_kernel(application).boot() as booted:
        assert booted.container.has(MailerInterface)


async def test_an_email_is_signed_with_s_mime(tmp_path: Path) -> None:
    async with ScriptedSmtpServer() as server:
        application = Application(
            mailer=MailerConfig(
                dsn=f"smtp://localhost:{server.port}", smime_signer=_signer(tmp_path)
            )
        )
        received = await _sent(server, application, _email())

    assert verifies(received, authority().certificate)


async def test_an_email_is_signed_then_encrypted_for_the_configured_certificates(
    tmp_path: Path,
) -> None:
    encrypter = SmimeEncrypterConfig(certificates=_certificates(tmp_path))
    async with ScriptedSmtpServer() as server:
        application = Application(
            mailer=MailerConfig(
                dsn=f"smtp://localhost:{server.port}",
                smime_signer=_signer(tmp_path),
                smime_encrypter=encrypter,
            )
        )
        received = await _sent(server, application, _email(encrypt=True))

    for reader in _RECIPIENTS:
        assert verifies(decrypt(received, identity(reader)), authority().certificate)


async def test_an_email_is_encrypted_for_the_certificates_a_repository_service_finds(
    tmp_path: Path,
) -> None:
    repository = InMemorySmimeCertificateRepository(_certificates(tmp_path))
    encrypter = SmimeEncrypterConfig(
        repository=Reference(InMemorySmimeCertificateRepository, "certificates")
    )
    async with ScriptedSmtpServer() as server:
        application = Application(
            mailer=MailerConfig(dsn=f"smtp://localhost:{server.port}", smime_encrypter=encrypter),
            provided=[Provided(repository, qualifier="certificates")],
        )
        received = await _sent(server, application, _email(encrypt=True))

    assert b"Line three" in decrypt(received, identity("hidden@example.com"))


async def test_a_transport_is_capped_by_its_rate_limiter() -> None:
    limiter = LimiterConfig("fixed_window", limit=1, interval="1 minute", storage="in-memory")
    application = Application(
        mailer=MailerConfig(
            transports={"main": TransportConfig("null://null", rate_limiter="mail")}
        ),
        peers={"rate_limiter": RateLimiterConfig(limiters={"mail": limiter})},
    )

    async with await mailer_kernel(application).boot() as booted:
        mailer = await booted.container.get(MailerInterface)
        await mailer.send(_email())

        with pytest.raises(RateLimitExceededError):
            await mailer.send(_email())
