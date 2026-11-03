"""``mailer:test`` sends a plain email straight through the transport it is built with."""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING, cast, final

import pytest
from typing_extensions import override
from xtr_console import (
    Application,
    CommandInvokerInterface,
    CommandTester,
    ExitCode,
    MissingContainerError,
)
from xtr_mime import Email

from tests.support.scripted_smtp_server import ScriptedSmtpServer
from tests.support.scripted_transport import ScriptedTransport
from xtr_mailer import Transport, TransportError
from xtr_mailer.command import MailerTestCommand
from xtr_mailer.transport import NullTransport, Transports

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from xtr_console import CommandArguments, CommandDescriptor, CommandSignature
    from xtr_mime import RawMessage

    from xtr_mailer.transport import TransportInterface

pytestmark = pytest.mark.anyio

_USER = "smtp-user-7f3a"
_PASSWORD = "p4ss-7f3a-w0rd"


@final
class _BuildWithTransport(CommandInvokerInterface):
    """Builds the command with the transport a container would have supplied."""

    def __init__(self, transport: TransportInterface) -> None:
        self._transport = transport

    @override
    async def invoke(
        self,
        command: CommandDescriptor,
        signature: CommandSignature,
        arguments: CommandArguments,
    ) -> object:
        del command, signature
        # The arguments come parsed off the command line, typed only as objects.
        call = cast("Callable[..., Awaitable[object]]", MailerTestCommand(self._transport))
        return await call(*arguments.args, **arguments.kwargs)


def _tester(transport: TransportInterface) -> CommandTester:
    application = Application(catch_exceptions=False)
    application.use_invoker(_BuildWithTransport(transport))
    return CommandTester(application, "mailer:test")


def _printed(tester: CommandTester) -> str:
    """What the run printed, its lines joined back where the console wrapped them."""
    return " ".join((tester.display + tester.error_display).split())


def _email(received: list[RawMessage]) -> Email:
    [message] = received
    assert isinstance(message, Email)
    return message


async def test_it_sends_the_email_its_options_describe() -> None:
    transport = ScriptedTransport("main")

    code = await _tester(transport).execute(
        [
            "to@example.com",
            "--from",
            "from@example.com",
            "--subject",
            "Foobar",
            "--body",
            "Lorem ipsum dolor sit amet.",
        ]
    )

    email = _email(transport.received)
    assert code == ExitCode.SUCCESS
    assert [
        email.get_from()[0].get_address(),
        email.get_to()[0].get_address(),
        email.get_subject(),
        email.get_text_body(),
    ] == ["from@example.com", "to@example.com", "Foobar", "Lorem ipsum dolor sit amet."]


async def test_it_names_the_transport_to_send_through() -> None:
    transport = ScriptedTransport("main")

    _ = await _tester(transport).execute(["to@example.com", "--transport", "foobar"])

    assert _email(transport.received).get_headers().get_header_body("X-Transport") == "foobar"


async def test_options_left_out_send_from_the_default_sender_subject_and_body() -> None:
    transport = ScriptedTransport("main")

    _ = await _tester(transport).execute(["to@example.com"])

    email = _email(transport.received)
    assert [email.get_from()[0].get_address(), email.get_subject(), email.get_text_body()] == [
        "from@example.org",
        "Testing transport",
        "Testing body",
    ]


@pytest.mark.parametrize("args", [[], ["--transport", ""]], ids=["left-out", "empty"])
async def test_without_a_transport_name_the_email_names_none(args: list[str]) -> None:
    transport = ScriptedTransport("main")

    _ = await _tester(transport).execute(["to@example.com", *args])

    assert not _email(transport.received).get_headers().has("X-Transport")


async def test_the_transports_send_it_through_the_one_named() -> None:
    main, other = ScriptedTransport("main"), ScriptedTransport("other")

    code = await _tester(Transports({"main": main, "other": other})).execute(
        ["to@example.com", "--transport", "other"]
    )

    assert code == ExitCode.SUCCESS
    assert main.received == []
    assert len(other.sent) == 1


async def test_a_sent_email_prints_nothing() -> None:
    tester = _tester(NullTransport())

    code = await tester.execute(["to@example.com"])

    assert code == ExitCode.SUCCESS
    assert (tester.display, tester.error_display) == ("", "")


async def test_an_unknown_transport_name_is_reported_and_nothing_is_sent() -> None:
    main = ScriptedTransport("main")
    tester = _tester(Transports({"main": main}))

    code = await tester.execute(["to@example.com", "--transport", "missing"])

    printed = _printed(tester)
    assert code == ExitCode.FAILURE
    assert 'The "missing" transport does not exist (available transports: "main").' in printed
    assert main.received == []


@pytest.mark.parametrize(
    "args",
    [["not an address"], ["to@example.com", "--from", "not an address"]],
    ids=["recipient", "sender"],
)
async def test_an_invalid_address_is_reported_and_nothing_is_sent(args: list[str]) -> None:
    transport = ScriptedTransport("main")
    tester = _tester(transport)

    code = await tester.execute(args)

    assert code == ExitCode.FAILURE
    assert 'Email "not an address" does not comply with addr-spec of RFC 5322.' in _printed(tester)
    assert transport.received == []


async def test_a_transport_failure_is_reported() -> None:
    error = TransportError('Connection could not be established with host "mail.example.com:465".')
    tester = _tester(ScriptedTransport("main", [error]))

    code = await tester.execute(["to@example.com"])

    assert code == ExitCode.FAILURE
    assert str(error) in _printed(tester)


async def test_without_a_container_the_console_names_the_transport_it_needs() -> None:
    tester = CommandTester(Application(catch_exceptions=False), "mailer:test")

    with pytest.raises(MissingContainerError, match="transport"):
        _ = await tester.execute(["to@example.com"])


async def test_it_sends_through_an_smtp_server() -> None:
    async with ScriptedSmtpServer() as server:
        transports = Transport.from_dsns({"main": f"smtp://127.0.0.1:{server.port}?timeout=5"})

        code = await _tester(transports).execute(["to@example.com", "--subject", "Smoke test"])
        await transports.close()

    assert code == ExitCode.SUCCESS
    assert [line for line in server.commands if line.startswith(("MAIL", "RCPT"))] == [
        "MAIL FROM:<from@example.org>",
        "RCPT TO:<to@example.com>",
    ]
    [received] = server.messages
    assert b"\r\nSubject: Smoke test\r\n" in received


async def test_a_login_the_smtp_server_refuses_is_reported_without_the_credentials() -> None:
    async with ScriptedSmtpServer() as server:
        server.capabilities = ["AUTH PLAIN LOGIN"]
        server.replies["AUTH"] = ["535 5.7.8 Authentication credentials invalid"] * 2
        transports = Transport.from_dsns(
            {"main": f"smtp://{_USER}:{_PASSWORD}@127.0.0.1:{server.port}?timeout=5"}
        )
        tester = _tester(transports)

        code = await tester.execute(["to@example.com"])
        await transports.close()

    printed = _printed(tester)
    encoded = [
        base64.b64encode(credential.encode()).decode()
        for credential in (_USER, _PASSWORD, f"{_USER}\0{_USER}\0{_PASSWORD}")
    ]
    assert code == ExitCode.FAILURE
    assert any(line.startswith("AUTH PLAIN ") for line in server.commands)
    assert (
        'Failed to authenticate on SMTP server using the following authenticators: "PLAIN", '
        '"LOGIN".' in printed
    )
    assert [shown for shown in (_USER, _PASSWORD, *encoded) if shown in printed] == []
