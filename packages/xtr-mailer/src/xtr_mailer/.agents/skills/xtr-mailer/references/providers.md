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

Every scheme advertised must be one `_get_supported_schemes` lists: the factory below serves
`acme` and `acme+api`, so a library serving the other two advertises them and lists them there as
well.

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
from http import HTTPStatus
from typing import TYPE_CHECKING

from typing_extensions import override

from xtr_mailer.exception import HttpTransportError
from xtr_mailer.transport import AbstractApiTransport

if TYPE_CHECKING:
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_client_contracts import HttpClientInterface, HttpResponseInterface
    from xtr_logging_contracts import LoggerInterface
    from xtr_mime import Email

    from xtr_mailer import Envelope, SentMessage


class AcmeApiTransport(AbstractApiTransport):
    """Hands Acme's API the fields of each email, and keeps the id it answers with."""

    def __init__(
        self,
        key: str,
        http_client: HttpClientInterface,
        event_dispatcher: EventDispatcherInterface | None = None,
        logger: LoggerInterface | None = None,
    ) -> None:
        super().__init__(http_client, event_dispatcher, logger)
        self._key = key

    @override
    def __str__(self) -> str:
        return f"acme+api://{self._endpoint()}"  # never the key

    @override
    async def _do_send_api(
        self, sent_message: SentMessage, email: Email, envelope: Envelope
    ) -> HttpResponseInterface:
        async with await self._http_client.request(
            "POST",
            f"https://{self._endpoint()}/v1/send",
            auth_bearer=self._key,
            json=self._payload(email, envelope),
        ) as response:
            answered = await response.to_array(throw=False)
            if response.get_status_code() != HTTPStatus.OK:
                raise HttpTransportError(
                    f"Unable to send an email: {answered.get('message')}.",
                    response,
                    response.get_status_code(),
                )
            sent_message.set_message_id(str(answered.get("id")))
            return response

    def _endpoint(self) -> str:
        """Return the host the DSN named, and the port when it named one."""
        host = self._host if self._host is not None else "api.acme.test"
        return host if self._port is None else f"{host}:{self._port}"

    def _payload(self, email: Email, envelope: Envelope) -> dict[str, object]:
        """Build Acme's own fields, the provider-neutral headers among them."""
        payload: dict[str, object] = {
            "from": envelope.get_sender().get_address(),
            "to": [address.get_address() for address in self._get_recipients(email, envelope)],
            "subject": email.get_subject() or "",
            "text": email.get_text_body(),
        }
        tag = email.get_headers().get("X-Tag")
        if tag is not None:
            payload["campaign"] = tag.get_body_as_string()
        return payload
```

- `_do_send_api` returns the provider's answer: the base appends its request line and status to
  the sent message's debug log. Read the body inside `async with`, so the connection and the body
  are let go, and return the response from inside the block.
- Raise `HttpTransportError` for a status the provider refused the email with, carrying the
  response and the status. Let the HTTP client's own errors go: the base turns a provider it
  cannot reach, a transfer that timed out and a body it cannot read into a `TransportError` — what
  `failover(...)` and `roundrobin(...)` move on from — without repeating the client's message,
  which names the URL. Chaining the client's error yourself would carry that URL into the chain.
- Set the message id yourself: each provider answers with its own.
- `_host` and `_port` are what the factory set from the DSN, `None` meaning the provider's own.
- `_get_recipients(email, envelope)` gives the envelope's recipients without the email's copy and
  hidden recipients, which go in fields of their own.
- Translate `X-Tag`, `X-Metadata-<key>` and `X-Track` into the provider's names, and
  drop `X-Track` from what you send. Work on a copy — never mutate the caller's email.
- The string form names the endpoint and the options, never a credential, and neither does any
  error or log line.

## The factory

```python
from collections.abc import Sequence
from typing import TYPE_CHECKING

from typing_extensions import override

from xtr_mailer.exception import UnsupportedSchemeError
from xtr_mailer.transport import AbstractTransportFactory

if TYPE_CHECKING:
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_client_contracts import HttpClientInterface
    from xtr_logging_contracts import LoggerInterface

    from xtr_mailer.transport import Dsn, TransportInterface


class AcmeTransportFactory(AbstractTransportFactory):
    """Builds Acme's transports; the client is required, so discovery refuses without one."""

    def __init__(
        self,
        http_client: HttpClientInterface,
        event_dispatcher: EventDispatcherInterface | None = None,
        logger: LoggerInterface | None = None,
    ) -> None:
        super().__init__(event_dispatcher, http_client, logger)
        self._client = http_client

    @override
    def create(self, dsn: Dsn) -> TransportInterface:
        if not self.supports(dsn):
            raise UnsupportedSchemeError(dsn.scheme, "acme", self._get_supported_schemes())
        key = self._get_user(dsn)  # IncompleteDsnError when missing
        transport = AcmeApiTransport(key, self._client, self._event_dispatcher, self._logger)
        if dsn.get_boolean_option("sandbox"):
            _ = transport.set_host("sandbox.acme.test")
        elif dsn.host != "default":
            _ = transport.set_host(dsn.host).set_port(dsn.get_port())
        return transport

    @override
    def _get_supported_schemes(self) -> Sequence[str]:
        return ("acme", "acme+api")
```

Declaring `http_client` required in a constructor of its own is what makes discovery refuse to
build the factory without a client, naming the scheme, rather than building transports that fail
on their first email. It also gives the factory a client of a type that is not optional, which
the base keeps as `_http_client` for a factory whose transports may do without one.

`default` as the host means the provider's own; any other host overrides it, which is how a test
points the transport at a local server. The parts of the DSN are `dsn.scheme`, `dsn.host`,
`dsn.user`, `dsn.password` and `dsn.get_port(default=None)`; read an option with
`dsn.get_option("region", "us")` and `dsn.get_boolean_option("sandbox")`, which raises
`InvalidArgumentError` on a value that is no boolean. A credential the scheme needs is read with
`_get_user` and `_get_password`, each raising `IncompleteDsnError` when the DSN leaves it out.

## Tests

```python
import pytest
from xtr_http_client import MockHttpClient, MockResponse
from xtr_mime import Email

from xtr_mailer import Dsn
from xtr_mailer.exception import HttpTransportError
from xtr_mailer.testing import USER, FactoryCases, assert_factory_cases

pytestmark = pytest.mark.anyio


def test_the_factory_does_what_every_factory_owes() -> None:
    assert_factory_cases(
        FactoryCases(
            create_factory=lambda: AcmeTransportFactory(MockHttpClient()),
            supports=[(Dsn("acme", "default"), True), (Dsn("other", "default"), False)],
            create=[
                (Dsn("acme", "default", USER), AcmeApiTransport(USER, MockHttpClient())),
                (
                    Dsn("acme+api", "acme.example.test", USER, port=8443),
                    AcmeApiTransport(USER, MockHttpClient())
                    .set_host("acme.example.test")
                    .set_port(8443),
                ),
            ],
            unsupported_scheme=[(Dsn("other", "default", USER), "not supported")],
            incomplete_dsn=[Dsn("acme", "default")],
        )
    )


async def test_the_api_is_called_with_the_email_s_fields() -> None:
    requests: list[tuple[str, str, object]] = []

    def answer(method: str, url: str, options: object) -> MockResponse:
        requests.append((method, url, options))
        return MockResponse(b'{"id": "acme-17"}')

    transport = AcmeApiTransport("KEY", MockHttpClient(answer))
    email = Email().from_("shop@example.com").to("ana@example.com").text("On its way.")

    sent = await transport.send(email)

    assert sent is not None
    assert sent.get_message_id() == "acme-17"
    [(method, url, options)] = requests
    assert (method, url) == ("POST", "https://api.acme.test/v1/send")
    assert isinstance(options, dict)
    assert options["auth_bearer"] == "KEY"
    assert options["json"]["to"] == ["ana@example.com"]
    assert "KEY" not in str(transport)
    assert "KEY" not in sent.get_debug()


async def test_a_status_the_provider_refuses_with_is_a_transport_error() -> None:
    client = MockHttpClient(MockResponse(b'{"message": "no"}', {"http_code": 422}))
    transport = AcmeApiTransport("KEY", client)
    email = Email().from_("shop@example.com").to("ana@example.com").text("Hi")

    with pytest.raises(HttpTransportError) as caught:
        _ = await transport.send(email)

    assert str(caught.value) == "Unable to send an email: no."
    assert caught.value.code == 422
    assert "KEY" not in caught.value.debug
```

`USER` and `PASSWORD` come from `xtr_mailer.testing`: credentials holding a `$`, which must reach
the transport as they were written. `FactoryCases` compares two transports built alike by
`str()` unless `read_state` reads something else, so a setting the string form does not show is
read there.

Then pin a client failure mapped to `TransportError`, and check that no credential appears in
`str(transport)`, in an error or in the debug transcript. Assert decoded headers, never rendered
bytes.

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
