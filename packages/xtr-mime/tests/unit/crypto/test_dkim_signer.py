"""A DKIM signer adds a signature a verifier accepts, over the bytes the message is sent as.

Every signature is checked with dkimpy's verifier against the test key's public half. The
signature's ``t=`` and ``b=`` change with the clock, so tags are compared, never the field.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Final

import pytest

from tests.support.dkim_extra import require_dkim_extra

require_dkim_extra()

# Imported after the skip: without the extra the key helper does not import.
from tests.support.dkim_keys import DOMAIN, SELECTOR, dkim_key  # noqa: E402 -- see above.
from tests.support.dkim_signing import (  # noqa: E402 -- see above.
    field_names,
    signed_names,
    tags,
    wire,
)
from tests.support.dkim_signing import signer as _signer  # noqa: E402 -- see above.
from xtr_mime import (  # noqa: E402 -- see above.
    Address,
    Email,
    Headers,
    InvalidArgumentError,
    Message,
    MimeRuntimeError,
    TextPart,
)
from xtr_mime.crypto import DkimOptions, DkimSigner  # noqa: E402 -- see above.
from xtr_mime.header import MailboxListHeader  # noqa: E402 -- see above.

_BODY: Final = (
    "Some body \n \n This \r\n\r\n is really interesting and at the same time very long line to "
    "see if everything works as expected, does it?\r\n\r\n\r\n\r\n"
)
_UPSTREAM_BODY_HASH: Final = "JC6qmm3afMaxL3Rm1YHxrzIpqiUuB7aAarWMcZfuca4="
_CANONS: Final = [("simple", "simple"), ("simple", "relaxed"), ("relaxed", "relaxed")]
_CANONS_ALL: Final = [*_CANONS, ("relaxed", "simple")]


def _email(text: str = _BODY) -> Email:
    return (
        Email()
        .from_(Address(f"fabien@{DOMAIN}", "Fabién"))
        .to("fabien.potencier@example.com")
        .subject("Tést")
        .text(text)
        .date(datetime(2005, 10, 15, tzinfo=timezone(timedelta(hours=2))))
    )


def _canon(body: str, header: str) -> DkimOptions:
    return DkimOptions().body_canon(body).header_canon(header).headers_to_ignore(["Message-ID"])


@pytest.mark.parametrize(("body", "header"), _CANONS_ALL)
def test_signing_keeps_what_the_body_renders_to_and_adds_a_signature(
    body: str, header: str
) -> None:
    message = _email()

    signed = _signer().sign(message, _canon(body, header))

    signed_body = signed.get_body()
    assert signed_body is not None
    assert signed_body.to_string() == message.get_body().to_string()
    assert signed.get_headers().has("DKIM-Signature")


@pytest.mark.parametrize(("body", "header"), _CANONS_ALL)
def test_the_signature_carries_the_tags_asked_for(body: str, header: str) -> None:
    found = tags(_signer().sign(_email(), _canon(body, header)))

    assert {key: found[key] for key in ("v", "q", "a", "bh", "d", "i", "s", "c")} == {
        "v": "1",
        "q": "dns/txt",
        "a": "rsa-sha256",
        "bh": _UPSTREAM_BODY_HASH,
        "d": DOMAIN,
        "i": f"@{DOMAIN}",
        "s": SELECTOR,
        "c": f"{header}/{body}",
    }
    assert re.fullmatch(r"\d+", found["t"])


def test_the_headers_signed_are_the_message_s_but_those_ignored_and_from_once_more() -> None:
    signed = _signer().sign(_email(), _canon("relaxed", "relaxed"))

    assert signed_names(signed) == ["from", "to", "subject", "date", "mime-version", "from"]


@pytest.mark.parametrize(("body", "header"), _CANONS_ALL)
def test_the_signature_verifies(body: str, header: str) -> None:
    signed = _signer().sign(_email(), _canon(body, header))

    assert dkim_key().verifies(wire(signed))


def test_signing_with_an_unsupported_algorithm_is_refused_before_the_message_is_read() -> None:
    signer = _signer(DkimOptions().algorithm("unsupported-value"))

    with pytest.raises(InvalidArgumentError) as raised:
        _ = signer.sign(Message())

    assert str(raised.value) == 'Invalid DKIM signing algorithm "unsupported-value".'


_CANONICALIZED: Final = [
    ("simple", "\r\n", ""),
    ("relaxed", "", ""),
    ("simple", "\r\n", "\r\n"),
    ("relaxed", "", "\r\n"),
    ("simple", "Some body\r\n", "Some body\r\n\r\n\r\n\r\n\r\n\r\n"),
    ("relaxed", "Some body\r\n", "Some body\r\n\r\n\r\n\r\n\r\n\r\n"),
    ("simple", "Some body\r\n", "Some body\r\n"),
    ("relaxed", "Some body\r\n", "Some body\r\n"),
    ("simple", "Some    body      with whitespaces\r\n", "Some    body      with whitespaces\r\n"),
    ("relaxed", "Some body with whitespaces\r\n", "Some    body      with whitespaces\r\n"),
]


@pytest.mark.parametrize(("canon", "canonical_body", "text"), _CANONICALIZED)
def test_the_body_is_hashed_canonicalized(canon: str, canonical_body: str, text: str) -> None:
    options = DkimOptions().body_canon(canon).body_show_length(True)

    signed = _signer().sign(_email(text), options)

    expected = base64.b64encode(hashlib.sha256(canonical_body.encode()).digest()).decode()
    assert (tags(signed)["bh"], tags(signed)["l"]) == (expected, str(len(canonical_body)))
    assert dkim_key().verifies(wire(signed))


def test_the_body_length_is_shown_only_when_asked() -> None:
    assert "l" not in tags(_signer().sign(_email()))


def test_an_option_set_off_for_one_signature_wins_over_the_signer_s() -> None:
    signer = _signer(DkimOptions().body_show_length(True))

    assert "l" not in tags(signer.sign(_email(), DkimOptions().body_show_length(False)))


def test_an_ed25519_signature_is_refused() -> None:
    signer = _signer(DkimOptions().algorithm(DkimSigner.ALGO_ED25519))

    with pytest.raises(RuntimeError) as raised:
        _ = signer.sign(_email())

    assert str(raised.value) == 'The "ed25519-sha256" DKIM signing algorithm is not supported yet.'


@pytest.mark.parametrize(
    "options", [DkimOptions().header_canon("nofws"), DkimOptions().body_canon("nofws")]
)
def test_an_unknown_canonicalization_is_refused(options: DkimOptions) -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = _signer().sign(_email(), options)

    assert str(raised.value) == 'Invalid DKIM canonicalization "nofws".'


def test_options_given_to_sign_win_over_the_signer_s_and_the_rest_are_kept() -> None:
    signer = _signer(DkimOptions().header_canon("simple").body_canon("simple"))

    signed = signer.sign(_email(), DkimOptions().body_canon("relaxed"))

    assert tags(signed)["c"] == "simple/relaxed"


@pytest.mark.parametrize("header", ["simple", "relaxed"])
def test_a_message_with_non_ascii_headers_and_an_attachment_verifies(header: str) -> None:
    message = _email().html("<p>Héllo wörld</p>").attach(b"\x00\x01binary", "dätä.bin")
    message = message.add_cc(Address(f"jürgen@{DOMAIN}", "Jürgen Ölmann"))

    signed = _signer(DkimOptions().header_canon(header)).sign(message)

    assert dkim_key().verifies(wire(signed))


@pytest.mark.parametrize(
    ("original", "changed"),
    [(b"interesting", b"interestinG"), (b"Subject: =?utf-8?q?T", b"Subject: =?utf-8?q?X")],
)
def test_a_changed_body_or_signed_header_no_longer_verifies(
    original: bytes, changed: bytes
) -> None:
    sent = wire(_signer().sign(_email()))
    assert original in sent

    assert not dkim_key().verifies(sent.replace(original, changed, 1))


def test_the_message_signed_is_left_as_it_was() -> None:
    message = _email()

    signed = _signer().sign(message)

    assert type(signed) is Message
    assert not message.get_headers().has("DKIM-Signature")
    assert b"DKIM-Signature" not in wire(message)


def test_the_bcc_of_the_message_signed_is_kept_for_the_envelope_and_never_sent() -> None:
    message = _email().add_cc("cc@example.com").add_bcc("hidden@example.com")

    signed = _signer().sign(message)

    bcc = signed.get_headers().get("Bcc")
    assert isinstance(bcc, MailboxListHeader)
    assert [address.get_address() for address in bcc.get_addresses()] == ["hidden@example.com"]
    sent = wire(signed)
    assert "bcc" not in [name.lower() for name in field_names(sent)]
    assert b"hidden@example.com" not in sent
    assert "bcc" not in [name.lower() for name in signed_names(signed)]
    assert dkim_key().verifies(sent)


def test_the_bcc_kept_changes_none_of_the_bytes_signed() -> None:
    signed = _signer().sign(_email().add_bcc("hidden@example.com"))
    without_bcc = copy.copy(signed)

    without_bcc.get_headers().remove("Bcc")

    assert wire(without_bcc) == wire(signed)


def test_the_signature_is_written_as_dkimpy_folded_it_until_its_value_changes() -> None:
    header = _signer().sign(_email()).get_headers().get("DKIM-Signature")
    assert header is not None
    assert "\r\n b=" in header.to_string()

    header.set_body("v=1; b=")

    assert header.to_string() == "DKIM-Signature: v=1; b="


def test_a_message_without_an_author_to_sign_cannot_be_signed() -> None:
    headers = Headers().add_mailbox_list_header("From", []).add_id_header("Message-ID", "a@b.c")
    message = Message(headers.add_mailbox_list_header("To", ["b@example.com"]), TextPart("Hi"))

    with pytest.raises(MimeRuntimeError) as raised:
        _ = _signer().sign(message)

    assert str(raised.value) == "Unable to sign DKIM hash: The From header field MUST be signed"
