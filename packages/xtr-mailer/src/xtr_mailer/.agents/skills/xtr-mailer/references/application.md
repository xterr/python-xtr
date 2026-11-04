# In an application

The bundle registers `Mailer` under `MailerInterface` and `Transports` under
`TransportInterface`, and builds nothing at boot. The DSN is read when either is first asked for
— the mailer takes the transports, so resolving one resolves both — and no socket is opened and
no key file read until an email is sent. The transports' sessions are closed when the container
closes.

```python
# app/config/bundles.py
from xtr_mailer.bundle import MailerBundle

BUNDLES = {MailerBundle: {"all": True}}
```

```python
# app/services/order_mail.py
from xtr_dependency_injection import as_service
from xtr_mailer import MailerInterface
from xtr_mime import Email


@as_service
class OrderMail:
    def __init__(self, mailer: MailerInterface) -> None:
        self.mailer = mailer

    async def shipped(self, address: str) -> None:
        await self.mailer.send(
            Email()
            .from_("shop@example.com")
            .to(address)
            .subject("Your order has shipped")
            .text("Your order is on its way.")
        )
```

## Configuration

`MailerConfig(dsn, transports, envelope, headers, tracking, dkim_signer, smime_signer,
smime_encrypter, http_client)`. With neither `dsn` nor `transports`, every email goes to
`null://null`; both together is an `InvalidArgumentError`.

```python
# app/config/packages/mailer.py
from xtr_dependency_injection import configure, env
from xtr_mailer.bundle import EnvelopeConfig, MailerConfig, TrackingConfig, TransportConfig


@configure
def mailer() -> MailerConfig:
    return MailerConfig(
        transports={
            "main": TransportConfig(env("MAILER_DSN"), rate_limiter="mail"),
            "marketing": TransportConfig(env("MAILER_MARKETING_DSN")),
        },
        envelope=EnvelopeConfig(
            sender="bounces@example.com",
            recipients=["staging@example.com"],
            allowed_recipients=[r"[^@]+@example\.com"],
        ),
        headers={"X-Campaign": "spring", "Reply-To": ["support@example.com"]},
        tracking=TrackingConfig(opens=True, clicks=True),
    )
```

Every field but `dsn`, `transports` and `http_client` is applied by a listener, so each needs the
xtr-event-dispatcher bundle. Configured without it the build is refused, naming the option:
`The "envelope" option needs the "event_dispatcher" bundle; install xtr-event-dispatcher beside
xtr-mailer.`

`rate_limiter` names a limiter the xtr-rate-limiter bundle configures; without that bundle the
build is refused, and a limiter named but not configured fails when the mailer is resolved, not
when an email is sent. A `failover(...)` or `roundrobin(...)` group takes none.

## Signing and encryption

```python
# app/config/packages/mailer.py
from xtr_dependency_injection import configure, env
from xtr_mailer.bundle import (
    DkimSignerConfig,
    MailerConfig,
    SmimeEncrypterConfig,
    SmimeSignerConfig,
)


@configure
def mailer() -> MailerConfig:
    return MailerConfig(
        dsn=env("MAILER_DSN"),
        dkim_signer=DkimSignerConfig(
            key="file://var/dkim/example.pem", domain="example.com", select="mail"
        ),
        smime_signer=SmimeSignerConfig(certificate="var/smime/shop.crt", key="var/smime/shop.key"),
        smime_encrypter=SmimeEncrypterConfig(
            certificates={"ana@example.com": "var/smime/ana.crt"},
            on_missing_certificate="fail",
        ),
    )
```

Each needs its extra, and says so at build otherwise —
`The "dkim" extra is required to use DKIM: uv add "xtr-mailer[dkim]".` `SmimeEncrypterConfig`
takes `certificates` or a `repository` `Reference` to one of yours implementing
`SmimeCertificateRepositoryInterface`, never both. Only an email carrying an `X-SMime-Encrypt`
header is encrypted.

## Queueing, logging, commands

- **Queue** by routing `xtr_mailer.messenger.SendEmailMessage` in
  `<app>/config/packages/messenger.py`. There is no option here for it.
- **Log** through the `mailer` channel the bundle adds to xtr-logging. Without that bundle
  nothing is logged and nothing complains.
- **`mailer:test <address>`** comes with the console bundle and sends straight to the transport,
  never through the bus. `debug:config mailer` shows what was resolved, never the DSN.
- **Record** every email with `MessageLoggerListener`, which the bundle registers in debug when
  the event dispatcher bundle is active.
