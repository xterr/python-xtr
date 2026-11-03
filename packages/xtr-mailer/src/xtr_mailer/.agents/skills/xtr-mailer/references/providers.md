# Writing a provider library

A provider library teaches the mailer one provider: the transport that hands an email over, and
the factory that builds it from a DSN. It is a package of its own, named `xtr-<provider>-mailer`
/ `xtr_<provider>_mailer`, installed beside `xtr-mailer` — and brought along by the
`xtr-mailer[<provider>]` extra, which names it.

## Layout

```
packages/xtr-acme-mailer/
├── pyproject.toml
├── README.md
├── LICENSE
├── src/xtr_acme_mailer/
│   ├── __init__.py
│   ├── py.typed
│   ├── transport/
│   │   ├── acme_transport_factory.py
│   │   ├── acme_api_transport.py      # form fields to the provider's API
│   │   ├── acme_http_transport.py     # the rendered MIME, posted
│   │   ├── acme_smtp_transport.py     # the provider's own SMTP relay
│   │   └── _acme_headers.py           # X-Tag / X-Metadata-* / X-Track translation
│   ├── recipe/                        # manifest.toml, [env] MAILER_DSN and a notes step
│   └── .agents/skills/xtr-acme-mailer/SKILL.md
└── tests/
```

Dependencies: `xtr-mailer`, `xtr-mime`, `xtr-http-client-contracts`, `typing-extensions`. The
dev group adds `xtr-http-client`, for `MockHttpClient`. **A provider library ships no bundle**:
its factory is found by the DSN's scheme.

## Advertise the factory

One entry point per scheme it serves, all naming the factory **class**:

```toml
[project.entry-points."xtr_mailer.transport_factories"]
acme = "xtr_acme_mailer:AcmeTransportFactory"
"acme+api" = "xtr_acme_mailer:AcmeTransportFactory"
"acme+https" = "xtr_acme_mailer:AcmeTransportFactory"
"acme+smtp" = "xtr_acme_mailer:AcmeTransportFactory"
```

Discovery builds it with `event_dispatcher=`, `http_client=` and `logger=` — the constructor of
`AbstractTransportFactory`. A factory needing anything else cannot be discovered; such a library
ships a bundle that registers it under `MAILER_TRANSPORT_FACTORY_TAG`
(`"mailer.transport_factory"`), and tagged factories are asked before the installed ones.

## Pick a base

| Base | Sends | Renders the email |
|---|---|---|
| `AbstractApiTransport` | the email's pieces as the provider's own fields | no — lazily, on first read of the `SentMessage` |
| `AbstractHttpTransport` | the rendered MIME message, posted whole | yes, before sending |
| `EsmtpTransport` | over the provider's SMTP relay | yes |

`AbstractApiTransport` renders nothing, so an email a mail server would refuse — a 1000-character
subject word — still reaches an API. Subclass it for a provider that takes fields, and
`AbstractHttpTransport` for one that takes a MIME body.

## The API transport

```python
from typing import ClassVar

from typing_extensions import override
from xtr_http_client_contracts.exception import TransportError as ClientError
from xtr_mime import Email

from xtr_mailer.envelope import Envelope
from xtr_mailer.exception import HttpTransportError, TransportError
from xtr_mailer.sent_message import SentMessage
from xtr_mailer.transport import AbstractApiTransport


class AcmeApiTransport(AbstractApiTransport):
    HOST: ClassVar[str] = "api.acme.test"

    def __init__(self, key: str, http_client, event_dispatcher=None, logger=None) -> None:
        super().__init__(http_client, event_dispatcher, logger)
        self._key = key

    @override
    def __str__(self) -> str:
        return f"acme+api://{self._get_endpoint()}"  # never the key

    @override
    async def _do_send_api(
        self, sent_message: SentMessage, email: Email, envelope: Envelope
    ) -> None:
        url = f"https://{self._get_endpoint()}/v1/send"
        try:
            response = await self._http_client.request("POST", url, body=self._payload(email))
        except ClientError as error:
            raise TransportError("Could not reach the remote Acme server.") from error
        async with response:
            answer = await response.to_array(throw=False)
            if response.get_status_code() != 200:
                raise HttpTransportError(
                    f"Unable to send an email: {answer.get('message')}.", response
                )
            sent_message.set_message_id(str(answer.get("id")))
```

- Read the answer inside `async with response`, so the connection and the body are let go.
- Raise `TransportError` for anything the provider refused or never answered — that is what
  `failover(...)` and `roundrobin(...)` move on from — and `HttpTransportError` when there is a
  response to carry.
- Set the message id yourself: each provider answers with its own.
- Translate `TagHeader`, `MetadataHeader` and `TrackingHeader` into the provider's names, and
  drop `X-Track` from what you send. Work on a copy — never mutate the caller's email.
- The string form names the endpoint and the options, never a credential, and neither does any
  error or log line.

## The factory

```python
from collections.abc import Sequence

from typing_extensions import override

from xtr_mailer.exception import UnsupportedSchemeError
from xtr_mailer.transport import AbstractTransportFactory, Dsn, TransportInterface


class AcmeTransportFactory(AbstractTransportFactory):
    @override
    def create(self, dsn: Dsn) -> TransportInterface:
        if not self.supports(dsn):
            raise UnsupportedSchemeError(dsn.scheme, "acme", self._get_supported_schemes())
        key = self._get_user(dsn)  # IncompleteDsnError when missing
        if dsn.scheme == "acme+smtp":
            return AcmeSmtpTransport(key, self._get_password(dsn), self._event_dispatcher)
        transport = AcmeApiTransport(key, self._http_client, self._event_dispatcher, self._logger)
        if dsn.host != "default":
            transport = transport.set_host(dsn.host).set_port(dsn.port)
        return transport

    @override
    def _get_supported_schemes(self) -> Sequence[str]:
        return ("acme", "acme+api", "acme+https", "acme+smtp")
```

`default` as the host means the provider's own; any other host overrides it, which is how a test
points the transport at a local server. Read options with `dsn.get_option` and
`dsn.get_required_option`; a non-boolean where a boolean belongs raises `InvalidArgumentError`.

## Tests

```python
from xtr_http_client import MockHttpClient

from xtr_mailer import Dsn
from xtr_mailer.testing import FactoryCases, assert_factory_cases


def test_the_factory_does_what_every_factory_owes() -> None:
    assert_factory_cases(
        FactoryCases(
            create_factory=lambda: AcmeTransportFactory(http_client=MockHttpClient()),
            supports=[(Dsn("acme", "default"), True), (Dsn("other", "default"), False)],
            create=[(Dsn("acme", "default", "KEY"), AcmeApiTransport("KEY", MockHttpClient()))],
            unsupported_scheme=[(Dsn("other", "default"), None)],
            incomplete_dsn=[Dsn("acme", "default")],
        )
    )
```

Then pin the exact request with a `MockHttpClient` whose callable checks the method, URL, headers
and body; every status the provider answers mapped to `HttpTransportError`; a client failure
mapped to `TransportError`; and that no credential appears in `str(transport)`, in an error or in
the debug transcript. Assert decoded headers, never rendered bytes.

## Outside the package

- A row in the core's `UnsupportedSchemeError` table (`scheme` → distribution), so a missing
  install is named, and an `[project.optional-dependencies] acme = ["xtr-acme-mailer..."]` extra
  in `xtr-mailer`, so `uv add "xtr-mailer[acme]"` works.
- A row in the core README's *Providers* table.
- The root `pyproject.toml` workspace source, `CREDITS.md`, the root README table and graph.
- A recipe: `[env] MAILER_DSN = "acme+api://KEY@default"` and a `notes.steps` line saying to set
  it — no `[bundles]`, no `[files]` — advertised as
  `[project.entry-points."xtr_recipes"] acme = "xtr_acme_mailer.recipe"`. The README's
  *Use in an application* lists Install, Recipe, Configure, Environment, Remove and Check, and
  points to xtr-mailer's for the rest.
