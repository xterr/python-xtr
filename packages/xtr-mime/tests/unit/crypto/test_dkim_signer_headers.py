"""Which headers a DKIM signature covers, and where the signature goes among them."""

from __future__ import annotations

import pytest

from tests.support.dkim_extra import require_dkim_extra

require_dkim_extra()

# Imported after the skip: without the extra these modules do not import.
import dkim  # noqa: E402 -- see above.

from tests.support.dkim_keys import DOMAIN, dkim_key  # noqa: E402 -- see above.
from tests.support.dkim_signing import (  # noqa: E402 -- see above.
    field_names,
    signed_names,
    signer,
    tags,
    wire,
)
from xtr_mime import Email, InvalidArgumentError  # noqa: E402 -- see above.
from xtr_mime.crypto import DkimOptions  # noqa: E402 -- see above.


def _email() -> Email:
    return Email().from_(f"fabien@{DOMAIN}").to("b@example.com").subject("Hi").text("Body")


def test_return_path_and_x_transport_are_never_signed_and_from_always_is() -> None:
    message = _email().return_path(f"bounce@{DOMAIN}")
    _ = message.get_headers().add_text_header("X-Transport", "main")
    _ = message.get_headers().add_text_header("X-Empty", "")

    signed = signer().sign(message, DkimOptions().headers_to_ignore(["FROM", "subject"]))

    assert signed_names(signed) == ["from", "to", "mime-version", "date", "message-id", "from"]
    assert dkim_key().verifies(wire(signed))


def test_headers_a_signer_is_advised_not_to_sign_are_signed_when_present() -> None:
    message = _email()
    _ = message.get_headers().add_text_header("Comments", "a note")

    signed = signer().sign(message)

    assert "comments" in signed_names(signed)
    assert dkim_key().verifies(wire(signed))


def test_a_from_added_above_the_signed_one_breaks_the_signature() -> None:
    sent = wire(signer().sign(_email()))

    tampered = b"From: mallory@example.com\r\n" + sent

    assert signed_names(signer().sign(_email())).count("from") == 2
    assert not dkim_key().verifies(tampered)


def test_a_second_signature_goes_on_top_and_both_verify() -> None:
    first = signer(selector="first").sign(_email())

    second = signer(selector="second").sign(first)

    sent = wire(second)
    assert [tags(second)["s"], field_names(sent)[:2]] == [
        "second",
        ["DKIM-Signature", "DKIM-Signature"],
    ]
    assert "dkim-signature" not in signed_names(second)
    assert dkim.DKIM(sent).verify(idx=0, dnsfunc=dkim_key().resolve)
    assert dkim.DKIM(sent).verify(idx=1, dnsfunc=dkim_key().resolve)


def test_a_header_name_holding_a_semicolon_is_refused_from_a_signature() -> None:
    message = _email()
    _ = message.get_headers().add_text_header("X-Odd;h", "value")

    with pytest.raises(InvalidArgumentError) as raised:
        _ = signer().sign(message)

    assert str(raised.value) == (
        'The "X-Odd;h" header cannot be signed with DKIM: a ";" in its name would end the '
        "list of headers signed."
    )


def test_a_header_name_holding_a_semicolon_is_signed_without_when_ignored() -> None:
    message = _email()
    _ = message.get_headers().add_text_header("X-Odd;h", "value")

    signed = signer(DkimOptions().headers_to_ignore(["x-odd;h"])).sign(message)

    assert dkim_key().verifies(wire(signed))
