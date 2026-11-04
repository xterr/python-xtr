from __future__ import annotations

import pytest
from xtr_dependency_injection import ContainerBuilder, bundle_active
from xtr_dependency_injection.exception import ServiceResolutionError
from xtr_dependency_injection.testing import assert_zero_config
from xtr_mime import Email
from xtr_rate_limiter import LimiterConfig
from xtr_rate_limiter.bundle import RateLimiterConfig

from tests.support.mailer_kernel import Application, mailer_kernel
from xtr_mailer import Mailer, MailerInterface
from xtr_mailer.bundle import (
    DkimSignerConfig,
    MailerBundle,
    MailerConfig,
    SmimeEncrypterConfig,
    SmimeSignerConfig,
    TransportConfig,
)
from xtr_mailer.bundle import mailer_bundle as bundle_module
from xtr_mailer.event_listener import MessageLoggerListener
from xtr_mailer.exception import LogicError

pytestmark = pytest.mark.anyio

_CAPPED = MailerConfig(transports={"main": TransportConfig("null://null", rate_limiter="mail")})
_LIMIT = LimiterConfig("fixed_window", limit=1, interval="1 minute", storage="in-memory")
_LIMITERS = RateLimiterConfig(limiters={"mail": _LIMIT})


async def test_it_builds_and_boots_with_no_configuration() -> None:
    await assert_zero_config(MailerBundle)


async def test_with_no_configuration_every_email_is_discarded() -> None:
    async with await mailer_kernel().boot() as booted:
        mailer = await booted.container.get(MailerInterface)
        await mailer.send(Email().from_("a@example.com").to("b@example.com").text("Hi"))
        logger = await booted.container.get(MessageLoggerListener)

    assert isinstance(mailer, Mailer)
    assert [event.get_transport() for event in logger.get_events().get_events()] == ["null://"]


def test_a_rate_limiter_without_the_rate_limiter_bundle_fails_the_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def active(builder: ContainerBuilder, name: str) -> bool:
        return name != "rate_limiter" and bundle_active(builder, name)

    monkeypatch.setattr(bundle_module, "bundle_active", active)

    with pytest.raises(LogicError) as caught:
        _ = mailer_kernel(Application(mailer=_CAPPED)).build()

    assert str(caught.value) == (
        'The "main" transport is capped by the "mail" rate limiter; install xtr-rate-limiter '
        "beside xtr-mailer and configure the limiter."
    )


def test_an_http_client_without_the_http_client_bundle_fails_the_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def active(builder: ContainerBuilder, name: str) -> bool:
        return name != "http_client" and bundle_active(builder, name)

    monkeypatch.setattr(bundle_module, "bundle_active", active)

    with pytest.raises(LogicError) as caught:
        _ = mailer_kernel(Application(mailer=MailerConfig(http_client="mailgun"))).build()

    assert str(caught.value) == (
        'The transports reach their provider through the "mailgun" HTTP client; install '
        "xtr-http-client beside xtr-mailer and configure the client."
    )


async def test_with_no_peer_active_every_email_is_sent_at_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def active(builder: ContainerBuilder, name: str) -> bool:
        del builder, name
        return False

    monkeypatch.setattr(bundle_module, "bundle_active", active)

    async with await mailer_kernel().boot() as booted:
        mailer = await booted.container.get(MailerInterface)
        await mailer.send(Email().from_("a@example.com").to("b@example.com").text("Hi"))

    assert isinstance(mailer, Mailer)
    assert (mailer._message_bus, mailer._event_dispatcher) == (None, None)


async def test_a_rate_limiter_that_is_not_configured_fails_the_first_email() -> None:
    async with await mailer_kernel(Application(mailer=_CAPPED)).boot() as booted:
        with pytest.raises(ServiceResolutionError) as caught:
            _ = await booted.container.get(MailerInterface)

    assert isinstance(caught.value.__cause__, LogicError)
    assert str(caught.value.__cause__) == (
        'The "main" transport is capped by the "mail" rate limiter, which is not configured.'
    )


async def test_a_rate_limiter_on_a_group_of_transports_fails_the_first_email() -> None:
    group = TransportConfig("failover(null://a null://b)", rate_limiter="mail")
    application = Application(
        mailer=MailerConfig(transports={"main": group}), peers={"rate_limiter": _LIMITERS}
    )

    async with await mailer_kernel(application).boot() as booted:
        with pytest.raises(ServiceResolutionError) as caught:
            _ = await booted.container.get(MailerInterface)

    assert isinstance(caught.value.__cause__, LogicError)
    assert str(caught.value.__cause__) == (
        'The "failover(null:// null://)" transport takes no rate limiter: a failover(...) or '
        "roundrobin(...) group is never capped."
    )


@pytest.mark.parametrize(
    ("config", "extra", "module"),
    [
        (MailerConfig(dkim_signer=DkimSignerConfig("k", "example.com", "s")), "dkim", "dkim"),
        (MailerConfig(smime_signer=SmimeSignerConfig("c", "k")), "smime", "cryptography"),
        (
            MailerConfig(smime_encrypter=SmimeEncrypterConfig(certificates={"a@b.c": "a.crt"})),
            "smime",
            "cryptography",
        ),
    ],
)
def test_signing_without_its_extra_fails_the_build(
    monkeypatch: pytest.MonkeyPatch, config: MailerConfig, extra: str, module: str
) -> None:
    def locate(name: str) -> object:
        return None if name == module else name

    monkeypatch.setattr(bundle_module, "find_spec", locate)

    with pytest.raises(LogicError) as caught:
        _ = mailer_kernel(Application(mailer=config)).build()

    label = "DKIM" if extra == "dkim" else "S/MIME"
    assert str(caught.value) == (
        f'The "{extra}" extra is required to use {label}: uv add "xtr-mailer[{extra}]".'
    )
