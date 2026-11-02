from __future__ import annotations

import pytest
from xtr_mime import Address

from xtr_mailer import Envelope, InvalidArgumentError
from xtr_mailer.transport._sendmail_command import (
    delivery_arguments,
    is_interactive,
    piped_message,
    sendmail_arguments,
)


def _envelope(sender: str = "from@example.com", *recipients: str) -> Envelope:
    return Envelope(Address(sender), [Address(r) for r in recipients or ("to@example.com",)])


def test_a_command_is_split_as_a_shell_splits_words() -> None:
    assert sendmail_arguments("'/opt/my sendmail' -oi -t") == ["/opt/my sendmail", "-oi", "-t"]


def test_the_program_itself_does_not_pick_the_mode() -> None:
    with pytest.raises(InvalidArgumentError, match="Unsupported sendmail command flags"):
        _ = sendmail_arguments("-bs -x")


def test_a_long_command_is_cut_short_in_the_refusal() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = sendmail_arguments("/usr/sbin/sendmail " + "x" * 100_000)

    assert len(str(caught.value)) < 200


@pytest.mark.parametrize(
    ("command", "interactive"),
    [("/usr/sbin/sendmail -bs", True), ("/usr/sbin/sendmail -t", False)],
)
def test_bs_runs_sendmail_in_smtp_mode(command: str, interactive: bool) -> None:
    assert is_interactive(sendmail_arguments(command)) is interactive


def test_the_delivery_drops_t_and_names_the_envelope() -> None:
    arguments = delivery_arguments(
        ["/usr/sbin/sendmail", "-oi", "-t"], _envelope("a@example.com", "b@example.com", "c@x.org")
    )

    assert arguments == [
        "/usr/sbin/sendmail",
        "-oi",
        "-fa@example.com",
        "--",
        "b@example.com",
        "c@x.org",
    ]


def test_a_sender_the_command_gives_is_not_given_again() -> None:
    arguments = delivery_arguments(["/usr/sbin/sendmail", "-t", "-f", "x@y.z"], _envelope())

    assert arguments == ["/usr/sbin/sendmail", "-f", "x@y.z", "--", "to@example.com"]


def test_a_sender_with_spaces_stays_one_argument() -> None:
    arguments = delivery_arguments(["/usr/sbin/sendmail", "-t"], _envelope('"a b"@example.com'))

    assert arguments[1] == '-f"a b"@example.com'


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (["s", "-t"], b"a\n..b\n...c\n"),
        (["s", "-t", "-i"], b"a\n.b\n..c\n"),
        (["s", "-oi", "-t"], b"a\n.b\n..c\n"),
    ],
)
def test_a_piped_message_has_lf_endings_and_its_dots_doubled_unless_i(
    arguments: list[str], expected: bytes
) -> None:
    assert piped_message(b"a\r\n.b\r\n..c\r\n", arguments) == expected


def test_a_dot_starting_the_message_is_left_as_it_is() -> None:
    assert piped_message(b".a\r\n", ["s", "-t"]) == b".a\n"
