# Writing a provider library

A provider library — a *bridge* — teaches the notifier one provider: its transport, the factory
that builds it from a DSN, and an options builder. It is a package of its own, named
`xtr-<provider>-notifier` / `xtr_<provider>_notifier`, installed beside `xtr-notifier`.

## Layout

```
packages/xtr-acme-notifier/
├── pyproject.toml
├── README.md
├── LICENSE
├── src/xtr_acme_notifier/
│   ├── __init__.py
│   ├── py.typed
│   ├── acme_transport.py
│   ├── acme_transport_factory.py
│   ├── acme_options.py
│   ├── recipe/                  # manifest.toml: [env] ACME_DSN, a notes step
│   └── .agents/skills/xtr-acme-notifier/SKILL.md
└── tests/
```

Dependencies: `xtr-notifier`, `xtr-http-client-contracts`, `typing-extensions`. The dev group
adds `xtr-http-client`, for `MockHttpClient`. A bridge ships no bundle.

## Advertise the factory

One entry point per scheme, in the chatter's group for a chat provider or the texter's for an
SMS or push provider — both when it serves both:

```toml
[project.entry-points."xtr_notifier.chatter_transport_factories"]
acme = "xtr_acme_notifier:AcmeTransportFactory"
```

The entry point names the factory **class**. Discovery builds it with
`http_client=` and `event_dispatcher=` — the constructor of `AbstractTransportFactory`. A
factory needing anything else cannot be discovered; such a bridge ships a bundle that registers
it under `CHATTER_TRANSPORT_FACTORY_TAG` or `TEXTER_TRANSPORT_FACTORY_TAG`.

## The transport

```python
from typing import ClassVar

from typing_extensions import override

from xtr_notifier.exception import TransportError, UnsupportedMessageTypeError
from xtr_notifier.message import ChatMessage, MessageInterface, SentMessage
from xtr_notifier.transport import AbstractTransport


class AcmeTransport(AbstractTransport):
    HOST: ClassVar[str] = "api.acme.test"

    def __init__(self, token: str, channel: str, http_client, event_dispatcher=None) -> None:
        super().__init__(http_client, event_dispatcher)
        self._token = token
        self._channel = channel

    @override
    def __str__(self) -> str:
        return f"acme://{self._get_endpoint()}?channel={self._channel}"  # never the token

    @override
    def supports(self, message: MessageInterface) -> bool:
        return isinstance(message, ChatMessage) and (
            message.options is None or message.options.kind == "acme"
        )

    @override
    async def _do_send(self, message: MessageInterface) -> SentMessage:
        if not isinstance(message, ChatMessage):
            raise UnsupportedMessageTypeError(str(self), "ChatMessage", message)
        url = f"{self._get_http_scheme()}://{self._get_endpoint()}/post"
        response = await self._http_client.request("POST", url, json={"text": message.subject})
        if response.get_status_code() != 200:
            raise TransportError("Unable to post the Acme message.", response)
        return SentMessage(message, str(self))
```

- `send` is inherited: it announces the message, calls `_do_send`, and announces the outcome.
- Raise `TransportError` for anything the provider refused or never answered — it is what
  failover moves on from — and `UnsupportedMessageTypeError` for a message of another kind.
- The string form names the endpoint and the options, never a credential.

## The factory

```python
from collections.abc import Sequence

from typing_extensions import override

from xtr_notifier.exception import UnsupportedSchemeError
from xtr_notifier.transport import AbstractTransportFactory, Dsn


class AcmeTransportFactory(AbstractTransportFactory):
    @override
    def create(self, dsn: Dsn) -> AcmeTransport:
        if not self.supports(dsn):
            raise UnsupportedSchemeError(dsn.scheme, "acme", self._get_supported_schemes())
        transport = AcmeTransport(
            self._get_user(dsn),  # IncompleteDsnError when missing
            dsn.get_required_option("channel"),  # MissingRequiredOptionError
            self._http_client,
            self._event_dispatcher,
        )
        host = None if dsn.host == "default" else dsn.host
        return transport.set_host(host).set_port(dsn.port).set_ssl(self._get_ssl(dsn))

    @override
    def _get_supported_schemes(self) -> Sequence[str]:
        return ("acme",)
```

## Options

A builder implementing `MessageOptionsInterface` — a `recipient_id` property and
`to_options()` — renders a frozen `MessageOptions("acme", recipient_id, values)`. Keep `values`
JSON data, so a message carrying it crosses a message bus. The transport reads
`message.options.values`.

## Tests

Hold the transport and the factory to what every provider owes:

```python
import pytest
from xtr_http_client import MockHttpClient

from xtr_notifier.message import ChatMessage, SmsMessage
from xtr_notifier.testing import (
    FactoryCases,
    TransportCases,
    assert_factory_cases,
    assert_transport_cases,
)


def _transport() -> AcmeTransport:
    return AcmeTransport("TOKEN", "ops", MockHttpClient())


@pytest.mark.anyio
async def test_the_transport_does_what_every_transport_owes() -> None:
    await assert_transport_cases(
        TransportCases(
            create_transport=_transport,
            to_string=[("acme://api.acme.test?channel=ops", _transport())],
            supported=[ChatMessage("Hello")],
            unsupported=[SmsMessage("+33", "Hello")],
        )
    )


def test_the_factory_does_what_every_factory_owes() -> None:
    assert_factory_cases(
        FactoryCases(
            create_factory=lambda: AcmeTransportFactory(MockHttpClient()),
            supports=[(True, "acme://TOKEN@default"), (False, "other://TOKEN@default")],
            create=[("acme://api.acme.test?channel=ops", "acme://TOKEN@default?channel=ops")],
            unsupported_scheme=[("other://TOKEN@default?channel=ops", None)],
            incomplete_dsn=[("acme://default?channel=ops", "User is not set.")],
            missing_required_option=[("acme://TOKEN@default", 'The option "channel"')],
        )
    )
```

Then pin the exact request with a `MockHttpClient` whose callable checks the method, URL,
headers and body, and every error the provider answers mapped to `TransportError`.

## Outside the package

- A row in the core's `UnsupportedSchemeError` table (`scheme` → distribution), so a missing
  install is named.
- The root `pyproject.toml` workspace source, `CREDITS.md`, the root README table and graph.
- A recipe: `[env] ACME_DSN = "acme://TOKEN@default?channel=CHANNEL"` and a `notes.steps` line
  adding `acme=env("ACME_DSN")` to `chatter_transports` in `config/notifier.py`.
