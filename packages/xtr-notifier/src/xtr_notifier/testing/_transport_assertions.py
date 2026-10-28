"""Driving a provider transport over its cases."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

from xtr_notifier.exception import UnsupportedMessageTypeError

from ._failures import raise_failures

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_notifier.message import MessageInterface
    from xtr_notifier.transport import AbstractTransport

    from .transport_cases import TransportCases

__all__ = ["CUSTOM_HOST", "CUSTOM_PORT", "assert_transport_cases"]

#: The host a transport is pointed at to check its string form shows it.
CUSTOM_HOST: Final = "host.test"
#: The port a transport is pointed at to check its string form shows it.
CUSTOM_PORT: Final = 42

_HOST = re.compile(rf"^.*://({re.escape(CUSTOM_HOST)}|.*@{re.escape(CUSTOM_HOST)})")
_PORT = re.compile(rf"^.*://.*(@.*)?:{CUSTOM_PORT}((\?.*|/.*))?$")
_HOST_AND_PORT = re.compile(
    rf"^.*://({re.escape(CUSTOM_HOST)}|.*@{re.escape(CUSTOM_HOST)}):{CUSTOM_PORT}"
)


async def assert_transport_cases(cases: TransportCases) -> None:
    """Check a transport against every one of ``cases``.

    Beyond the cases, a transport pointed at :data:`CUSTOM_HOST` and
    :data:`CUSTOM_PORT` must show them in its string form, which is how an
    application tells a self-hosted provider from the default one::

        await assert_transport_cases(
            TransportCases(
                create_transport=lambda: AcmeTransport("TOKEN", MockHttpClient()),
                to_string=[("acme://api.acme.test", AcmeTransport("TOKEN", MockHttpClient()))],
                supported=[ChatMessage("Hello")],
                unsupported=[SmsMessage("+33", "Hello")],
            )
        )

    Raises:
        AssertionError: Listing every case the transport fails. Raised rather
            than asserted, so the check holds however the suite is run.
    """
    failures = [
        f'it reads "{transport}", not "{expected}"'
        for expected, transport in cases.to_string
        if str(transport) != expected
    ]
    failures.extend(
        f"it does not support {message!r}"
        for message in cases.supported
        if not cases.create_transport().supports(message)
    )
    for message in cases.unsupported:
        failures.extend(await _refusal_failures(cases.create_transport(), message))
    failures.extend(_endpoint_failures(cases.create_transport))
    raise_failures("transport", failures)


async def _refusal_failures(transport: AbstractTransport, message: MessageInterface) -> list[str]:
    """Return how ``transport`` fails to refuse ``message``."""
    failures = [f"it supports {message!r}"] if transport.supports(message) else []
    try:
        _ = await transport.send(message)
    except UnsupportedMessageTypeError:
        return failures
    except Exception as error:  # noqa: BLE001 -- any other outcome is the failure being reported
        outcome = f"raised {type(error).__name__}: {error}"
    else:
        outcome = "raised nothing"
    return [*failures, f"sending {message!r} {outcome}, not UnsupportedMessageTypeError"]


def _endpoint_failures(create_transport: Callable[[], AbstractTransport]) -> list[str]:
    """Return how the string form fails to show an overridden host and port."""
    failures: list[str] = []
    host = str(create_transport().set_host(CUSTOM_HOST))
    if not _HOST.match(host):
        failures.append(f'it reads "{host}" with the host set to "{CUSTOM_HOST}"')
    port = str(create_transport().set_port(CUSTOM_PORT))
    if not _PORT.match(port):
        failures.append(f'it reads "{port}" with the port set to {CUSTOM_PORT}')
    both = str(create_transport().set_host(CUSTOM_HOST).set_port(CUSTOM_PORT))
    if not _HOST_AND_PORT.match(both):
        failures.append(
            f'it reads "{both}" with the host set to "{CUSTOM_HOST}" and the port to {CUSTOM_PORT}'
        )
    return failures
