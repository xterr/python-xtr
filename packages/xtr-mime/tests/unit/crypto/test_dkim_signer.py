"""A DKIM signer adds a signature a verifier accepts, over the bytes the message is sent as.

Every signature is checked with dkimpy's verifier against the test key's public half. The
signature's ``t=`` and ``b=`` change with the clock, so tags are compared, never the field.
"""

from __future__ import annotations

import base64
import hashlib
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Final

import pytest

from tests.support.dkim_extra import require_dkim_extra

require_dkim_extra()

# Imported after the skip: without the extra the key helper does not import.
from tests.support.dkim_keys import DOMAIN, SELECTOR, dkim_key  # noqa: E402 -- see above.
from xtr_mime import (  # noqa: E402 -- see above.
    Address,
    Email,
    Headers,
    InvalidArgumentError,
    LogicError,
    Message,
    MimeRuntimeError,
    TextPart,
)
from xtr_mime.crypto import DkimOptions, DkimSigner  # noqa: E402 -- see above.

if TYPE_CHECKING:
    from pathlib import Path

    from xtr_mime import RawMessage

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


def _signer(options: DkimOptions | None = None) -> DkimSigner:
    return DkimSigner(dkim_key().pem(), DOMAIN, SELECTOR, default_options=options)


def _wire(message: RawMessage) -> bytes:
    return b"".join(message.to_iterable())


def _tags(message: Message) -> dict[str, str]:
    header = message.get_headers().get("DKIM-Signature")
    assert header is not None
    pairs = (tag.partition("=") for tag in header.get_body_as_string().split(";"))
    return {name.strip(): re.sub(r"\s+", "", value) for name, _, value in pairs}


def _signed_names(message: Message) -> list[str]:
    return [name.strip() for name in _tags(message)["h"].split(":")]


def _canon(body: str, header: str) -> DkimOptions:
    return DkimOptions().body_canon(body).header_canon(header).headers_to_ignore(["Message-ID"])


@pytest.mark.parametrize(("body", "header"), _CANONS_ALL)
def test_signing_keeps_the_body_and_adds_a_signature(body: str, header: str) -> None:
    message = _email()

    signed = _signer().sign(message, _canon(body, header))

    assert signed.get_body() is message.get_body()
    assert signed.get_headers().has("DKIM-Signature")


@pytest.mark.parametrize(("body", "header"), _CANONS_ALL)
def test_the_signature_carries_the_tags_asked_for(body: str, header: str) -> None:
    tags = _tags(_signer().sign(_email(), _canon(body, header)))

    assert {key: tags[key] for key in ("v", "q", "a", "bh", "d", "i", "s", "c")} == {
        "v": "1",
        "q": "dns/txt",
        "a": "rsa-sha256",
        "bh": _UPSTREAM_BODY_HASH,
        "d": DOMAIN,
        "i": f"@{DOMAIN}",
        "s": SELECTOR,
        "c": f"{header}/{body}",
    }
    assert re.fullmatch(r"\d+", tags["t"])


def test_the_headers_signed_are_the_message_s_but_those_ignored() -> None:
    signed = _signer().sign(_email(), _canon("relaxed", "relaxed"))

    assert _signed_names(signed) == ["from", "to", "subject", "date", "mime-version"]


@pytest.mark.parametrize(("body", "header"), _CANONS_ALL)
def test_the_signature_verifies(body: str, header: str) -> None:
    signed = _signer().sign(_email(), _canon(body, header))

    assert dkim_key().verifies(_wire(signed))


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
    assert (_tags(signed)["bh"], _tags(signed)["l"]) == (expected, str(len(canonical_body)))
    assert dkim_key().verifies(_wire(signed))


def test_the_body_length_is_shown_only_when_asked() -> None:
    assert "l" not in _tags(_signer().sign(_email()))


def test_an_option_set_off_for_one_signature_wins_over_the_signer_s() -> None:
    signer = _signer(DkimOptions().body_show_length(True))

    assert "l" not in _tags(signer.sign(_email(), DkimOptions().body_show_length(False)))


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

    assert _tags(signed)["c"] == "simple/relaxed"


def test_return_path_and_x_transport_are_never_signed_and_from_always_is() -> None:
    message = _email().return_path(f"bounce@{DOMAIN}")
    _ = message.get_headers().add_text_header("X-Transport", "main")
    _ = message.get_headers().add_text_header("X-Empty", "")

    signed = _signer().sign(message, DkimOptions().headers_to_ignore(["FROM", "subject"]))

    assert _signed_names(signed) == ["from", "to", "date", "mime-version", "message-id"]
    assert dkim_key().verifies(_wire(signed))


def test_headers_a_signer_is_advised_not_to_sign_are_signed_when_present() -> None:
    message = _email()
    _ = message.get_headers().add_text_header("Comments", "a note")

    signed = _signer().sign(message)

    assert "comments" in _signed_names(signed)
    assert dkim_key().verifies(_wire(signed))


@pytest.mark.parametrize("header", ["simple", "relaxed"])
def test_a_message_with_non_ascii_headers_and_an_attachment_verifies(header: str) -> None:
    message = _email().html("<p>Héllo wörld</p>").attach(b"\x00\x01binary", "dätä.bin")
    message = message.add_cc(Address(f"jürgen@{DOMAIN}", "Jürgen Ölmann"))

    signed = _signer(DkimOptions().header_canon(header)).sign(message)

    assert dkim_key().verifies(_wire(signed))


@pytest.mark.parametrize(
    ("original", "changed"),
    [(b"interesting", b"interestinG"), (b"Subject: =?utf-8?q?T", b"Subject: =?utf-8?q?X")],
)
def test_a_changed_body_or_signed_header_no_longer_verifies(
    original: bytes, changed: bytes
) -> None:
    wire = _wire(_signer().sign(_email()))
    assert original in wire

    assert not dkim_key().verifies(wire.replace(original, changed, 1))


def test_the_message_signed_is_left_as_it_was() -> None:
    message = _email()

    signed = _signer().sign(message)

    assert type(signed) is Message
    assert not message.get_headers().has("DKIM-Signature")
    assert b"DKIM-Signature" not in _wire(message)


def test_the_signature_is_written_as_dkimpy_folded_it_until_its_value_changes() -> None:
    header = _signer().sign(_email()).get_headers().get("DKIM-Signature")
    assert header is not None
    assert "\r\n b=" in header.to_string()

    header.set_body("v=1; b=")

    assert header.to_string() == "DKIM-Signature: v=1; b="


@pytest.mark.parametrize("prefix", ["", "file://"])
def test_the_key_is_read_from_a_file(tmp_path: Path, prefix: str) -> None:
    path = tmp_path / "dkim.pem"
    _ = path.write_text(dkim_key().pem())
    private_key = f"{prefix}{path}" if prefix else path

    signed = DkimSigner(private_key, DOMAIN, SELECTOR).sign(_email())

    assert dkim_key().verifies(_wire(signed))


def test_a_key_file_that_cannot_be_read_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "missing.pem"

    with pytest.raises(InvalidArgumentError) as raised:
        _ = DkimSigner(path, DOMAIN, SELECTOR)

    assert str(raised.value) == (
        f'Unable to load DKIM private key: the file "{path}" cannot be read: '
        "No such file or directory."
    )


def test_a_passphrase_protected_key_signs() -> None:
    signer = DkimSigner(dkim_key().pem("secret"), DOMAIN, SELECTOR, passphrase="secret")

    assert dkim_key().verifies(_wire(signer.sign(_email())))


@pytest.mark.parametrize(
    ("domain_name", "selector", "message"),
    [
        (
            "testdkim.example.net; s=x",
            SELECTOR,
            (
                'The DKIM domain name "testdkim.example.net; s=x" is not dot-separated labels '
                'of letters, digits, "-" and "_".'
            ),
        ),
        (
            DOMAIN,
            "s f\r\n",
            (
                'The DKIM selector "s f\\r\\n" is not dot-separated labels of letters, digits, '
                '"-" and "_".'
            ),
        ),
    ],
)
def test_a_domain_name_or_selector_that_is_not_dns_labels_is_refused(
    domain_name: str, selector: str, message: str
) -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = DkimSigner(dkim_key().pem(), domain_name, selector)

    assert str(raised.value) == message


def test_a_message_without_an_author_to_sign_cannot_be_signed() -> None:
    headers = Headers().add_mailbox_list_header("From", []).add_id_header("Message-ID", "a@b.c")
    message = Message(headers.add_mailbox_list_header("To", ["b@example.com"]), TextPart("Hi"))

    with pytest.raises(MimeRuntimeError) as raised:
        _ = _signer().sign(message)

    assert str(raised.value) == "Unable to sign DKIM hash: The From header field MUST be signed"


def test_without_the_extra_building_a_signer_names_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "dkim", None)
    monkeypatch.delitem(sys.modules, "xtr_mime.crypto._dkimpy", raising=False)

    with pytest.raises(LogicError) as raised:
        _ = _signer()

    assert str(raised.value) == 'The "dkim" extra is required to use DKIM: uv add "xtr-mime[dkim]".'
