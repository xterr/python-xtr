from __future__ import annotations

from xtr_mailer.transport.smtp._smtp_transcript import REDACTED, SmtpTranscript


def test_it_records_what_was_sent_and_each_line_of_the_reply() -> None:
    transcript = SmtpTranscript()

    transcript.record(None, "220 ready")
    transcript.record("EHLO client", "250-localhost\r\n250 8BITMIME")

    assert transcript.take() == "< 220 ready\n> EHLO client\n< 250-localhost\n< 250 8BITMIME\n"
    assert transcript.take() == ""


def test_a_concealed_secret_is_scrubbed_from_every_reply() -> None:
    transcript = SmtpTranscript()
    transcript.conceal("p4ss")

    assert transcript.scrub("535 bad p4ss") == f"535 bad {REDACTED}"


def test_the_identity_is_scrubbed_only_from_replies_to_an_auth_exchange() -> None:
    transcript = SmtpTranscript()
    transcript.conceal("p4ss", "me@example.org")

    assert transcript.scrub("550 <me@example.org> refused") == "550 <me@example.org> refused"
    assert transcript.scrub("535 me@example.org", authenticating=True) == f"535 {REDACTED}"


def test_the_longest_secret_is_scrubbed_first() -> None:
    transcript = SmtpTranscript()
    transcript.conceal("abc")
    transcript.learn("abcdef")

    assert transcript.scrub("x abcdef y abc") == f"x {REDACTED} y {REDACTED}"


def test_a_reset_forgets_the_lines_and_what_was_learned_but_keeps_what_was_concealed() -> None:
    transcript = SmtpTranscript()
    transcript.conceal("p4ss")
    transcript.learn("cGF5bG9hZA==")
    transcript.record("NOOP", "250 ok")

    transcript.reset()

    assert transcript.take() == ""
    assert transcript.scrub("cGF5bG9hZA== p4ss") == f"cGF5bG9hZA== {REDACTED}"


def test_empty_secrets_are_ignored() -> None:
    transcript = SmtpTranscript()
    transcript.conceal("", "")
    transcript.learn("")

    assert transcript.scrub("250 ok") == "250 ok"


def test_a_recorded_reply_is_scrubbed() -> None:
    transcript = SmtpTranscript()
    transcript.conceal("p4ss", "me")

    transcript.record("[redacted]", "235 hi me p4ss", authenticating=True)

    assert transcript.take() == f"> [redacted]\n< 235 hi {REDACTED} {REDACTED}\n"


def test_a_line_sent_while_authenticating_is_shown_redacted_and_learned() -> None:
    transcript = SmtpTranscript()

    shown = transcript.shown("cGF5bG9hZA==", authenticating=True)

    assert shown == REDACTED
    assert transcript.scrub("535 cGF5bG9hZA==") == f"535 {REDACTED}"


def test_an_auth_command_shows_its_mechanism_and_learns_its_initial_response() -> None:
    transcript = SmtpTranscript()

    shown = transcript.shown("AUTH PLAIN AHVzZXIAcw==", authenticating=False)

    assert shown == f"AUTH PLAIN {REDACTED}"
    assert transcript.scrub("535 AHVzZXIAcw==") == f"535 {REDACTED}"


def test_any_other_command_is_shown_as_it_is() -> None:
    assert SmtpTranscript().shown("AUTH LOGIN", authenticating=False) == "AUTH LOGIN"
