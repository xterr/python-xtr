"""The handler of every ping: it takes the default client, as a service calling out does."""

from __future__ import annotations

# The container reads the handler's annotations at runtime.
from xtr_dependency_injection import Injected  # noqa: TC002
from xtr_http_client_contracts import HttpClientInterface  # noqa: TC002
from xtr_messenger import as_message_handler

from .messages import Ping
from .services import Pings  # noqa: TC001


@as_message_handler(Ping)
async def ping(
    message: Ping, http_client: Injected[HttpClientInterface], pings: Injected[Pings]
) -> None:
    del http_client
    pings.numbers.append(message.number)
