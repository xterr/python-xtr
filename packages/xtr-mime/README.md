<div align="center">

# xtr-mime

**Build email messages — addresses, headers, text and HTML bodies, attachments and inline images — rendered to standard MIME by Python's own email package, signed with DKIM or S/MIME when asked.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

Python's `email` package writes correct MIME, but building a message with it means knowing which
part nests inside which, which header takes an address list and which takes a date, and when a
`Content-ID` has to match a `cid:` in the HTML. xtr-mime is the typed model on top: an `Email`
builder with addresses that are checked, headers that are typed values, attachments and inline
images that are put where they belong, and a message that is valid to send or refuses to
render. The `email` package still writes every byte — header encoding and folding included — so
what goes on the wire is what the standard library writes.

- **Typed all the way down.** `Address`, eleven header classes, parts and multiparts; nothing from
  the `email` package appears in a signature.
- **Checked addresses.** The mail grammar, international addresses (RFC 6532) and domains,
  without asking DNS anything.
- **Signing.** DKIM through dkimpy, S/MIME signing and encryption through cryptography — both
  optional extras.
- **Testing helpers** that read an email the way a test thinks about it, with no test framework
  imported.

## Install

```sh
uv add xtr-mime
```

| Extra | Brings | For |
|---|---|---|
| `dkim` | dkimpy, cryptography | `DkimSigner` |
| `smime` | cryptography | `SMimeSigner`, `SMimeEncrypter` |
| `magic` | python-magic | `MagicMimeTypeGuesser`, which also needs libmagic itself: `brew install libmagic`, `apt install libmagic1` |

`uv add "xtr-mime[dkim,smime]"` takes several. Without `dkim` or `smime`, the signers still
import; building one raises `LogicError` naming the extra to install. Without `magic` or
libmagic, `MagicMimeTypeGuesser` declines to guess.

## Quick start

```python
from xtr_mime import Address, Email

email = (
    Email()
    .from_(Address("shop@example.com", "Example Shop"))
    .to("ana@example.com")
    .subject("Your order has shipped")
    .text("Your order is on its way.")
    .html("<p>Your order is <strong>on its way</strong>.</p>")
)

wire = email.to_string()  # the whole message, CRLF line ends
assert "Subject: Your order has shipped\r\n" in wire
assert "Content-Type: multipart/alternative;" in wire
```

`from_` carries an underscore because `from` is a keyword; its getter is `get_from()`. Every other
setter is the header's name: `to`, `cc`, `bcc`, `reply_to`, `sender`, `return_path`, `date`,
`priority`; `add_to` and the like append. `to_iterable()` yields the same message as bytes, in
pieces, for a socket. Rendering adds `Date`, `Message-ID` and `MIME-Version`, and refuses an email
with no `From` or `Sender`, or no body (`LogicError`); `ensure_validity()` also refuses one naming
no recipient, as a mailer checks before sending.

### Attachments and inline images

```python
email = (
    Email()
    .from_("shop@example.com")
    .to("ana@example.com")
    .subject("Invoice A-17")
    .text("Your invoice is attached.")
    .html('<p><img src="cid:logo.png"> Your invoice is attached.</p>')
    .attach_from_path("invoice.pdf")  # read when the email is rendered
    .attach(b"order,total\nA-17,19.99\n", "order.csv", "text/csv")
    .embed_from_path("logo.png")  # shown where the HTML says cid:logo.png
)

wire = email.to_string()
assert "Content-Type: multipart/mixed;" in wire
assert "Content-Type: multipart/related;" in wire
assert 'Content-Disposition: attachment; name="invoice.pdf"; filename="invoice.pdf"' in wire
```

A file is named by its extension (`invoice.pdf` is `application/pdf`) unless `content_type` says
otherwise, and read only when the email is rendered. An embedded part is given a `Content-ID`, and
the `cid:` naming it in the HTML is rewritten to match.

### Text from HTML

```python
from xtr_mime import DefaultHtmlToTextConverter

converter = DefaultHtmlToTextConverter()
html = "<h1>Hello</h1>\n<p>Your order&nbsp;is   <b>on its way</b>.</p>\n<script>track()</script>"

assert converter.convert(html, "utf-8") == "Hello\nYour order is on its way."
```

The text alternative an HTML-only email is sent with. Implement `HtmlToTextConverterInterface`
for another converter; see [Known limitations](#known-limitations) for what this one keeps.

### Sign with DKIM

Needs the `dkim` extra.

```python
from pathlib import Path

from xtr_mime import DkimOptions, DkimSigner

signer = DkimSigner(Path("dkim.pem"), "example.com", "mail")
signed = signer.sign(email, DkimOptions().header_canon(DkimSigner.CANON_SIMPLE))

assert signed.to_string().startswith("DKIM-Signature: v=1; a=rsa-sha256; c=simple/relaxed;")
```

The key is PEM text, a path, or a string starting with `file://`, opened when the signer is built
(pass `passphrase=` for an encrypted one). The signature covers every header but `Return-Path`,
`X-Transport` and those `headers_to_ignore` names; sign the message last, after anything else that
changes it.
The signed message carries the field as a `FoldedHeader`, written byte for byte as it was folded —
as `simple` canonicalization needs — and its body as a `SignedBody`, the bytes signed;
`SignedBody.from_frozen` builds one again from what it holds, in another process.

### Sign and encrypt with S/MIME

Needs the `smime` extra.

```python
from xtr_mime import SMimeEncrypter, SMimeSigner

signed = SMimeSigner("signer.crt", "signer.key").sign(email)
encrypted = SMimeEncrypter("recipient.crt").encrypt(signed)

assert 'Content-Type: multipart/signed; protocol="application/x-pkcs7-signature";' in (
    signed.to_string()
)
assert 'Content-Type: application/pkcs7-mime; smime-type="enveloped-data";' in (
    encrypted.to_string()
)
```

`SMimeEncrypter` takes one certificate path or several, one per recipient. The headers stay
outside the encryption, readable, so the message can be delivered.

### MIME types

```python
from xtr_mime import MimeTypes

mime_types = MimeTypes({"application/mbox": ["mbox"]})

assert mime_types.get_extensions("image/jpeg")[0] == "jpg"
assert mime_types.get_mime_types("mbox") == ["application/mbox"]
assert mime_types.guess_mime_type("invoice.pdf") == "application/pdf"
```

The table is the standard library's built-in one, plus the extra map. `guess_mime_type` asks the
registered guessers first — `MagicMimeTypeGuesser`, which reads the file's content where libmagic
is installed, and any `register_guesser` adds — then falls back to the file's extension.

## Testing

`xtr_mime.testing` checks an email the way a test thinks about it, raising `AssertionError` with
what was expected and what was found. It imports no test framework.

```python
from xtr_mime import Email
from xtr_mime.testing import (
    assert_email_address_contains,
    assert_email_attachment_count,
    assert_email_header_same,
    assert_email_subject_contains,
    assert_email_text_body_contains,
)

email = (
    Email()
    .from_("shop@example.com")
    .to("ana@example.com")
    .subject("Your order has shipped")
    .text("Hello Ana")
    .attach(b"A-17", "order.txt", "text/plain")
)

assert_email_header_same(email, "To", "ana@example.com")
assert_email_address_contains(email, "To", "ana@example.com")
assert_email_subject_contains(email, "shipped")
assert_email_text_body_contains(email, "Ana")
assert_email_attachment_count(email, 1)
```

Most have a negated twin (`assert_email_header_not_same`, `assert_email_not_has_header`,
`assert_email_subject_not_contains`, `assert_email_text_body_not_contains`,
`assert_email_html_body_not_contains`). A check asked about something a message cannot have — the
subject of raw bytes — raises `LogicError`: the test is wrong, not the email. Pass `clock=` to
`Email` with xtr-clock's `MockClock` to freeze its `Date`.

## Use in an application

Everything adding this package to an application on
[xtr-dependency-injection](../xtr-dependency-injection) takes — and, read backwards, what
removing it undoes.

- **Install** — `uv add xtr-mime`; add `dkim`, `smime` or `magic` for what each brings. The
  container the bundle plugs into, xtr-dependency-injection, is the application's own.
- **Recipe** — `uv run xtr-recipes recipes:sync` does the *Activate* step below: it lists
  `MimeBundle`. There is no config file, environment or ignore line to write.
- **Activate** — `MimeBundle: {"all": True}` in `BUNDLES` in `<app>/config/bundles.py`, imported
  from `xtr_mime.bundle`.
- **Brings along** — nothing: the bundle requires no other.
- **Configure** — optional: with no configuration the table is the standard library's built-in
  one, asking every guesser **tagged** for it, and a class subclassing `MimeTypeGuesserInterface`
  is tagged without being told. Extensions the table lacks go in a
  `<app>/config/packages/mime.py` `@configure` function returning `MimeConfig` — see
  [Kernel / bundle](#kernel--bundle). They apply to the container's `MimeTypes` service only:
  a `File` attachment reads `MimeTypes.get_default()`, which the bundle never changes.
- **Environment** — nothing read from the environment.
- **Ignore** — nothing: the bundle writes no file into the project.
- **Remove** — drop the `BUNDLES` entry (`uv run xtr-recipes recipes:remove xtr-mime` does it, and
  there is no file of its own to take away), delete `<app>/config/packages/mime.py` if you wrote
  one, then `uv remove xtr-mime`.
- **Check** — `debug:bundles` shows `mime` as `listed` and `active`.

## Kernel / bundle

With xtr-dependency-injection in the application, list the bundle:

```python
# app/config/bundles.py
from xtr_mime.bundle import MimeBundle

BUNDLES = {MimeBundle: {"all": True}}
```

It registers:

| Service | Under | Built |
|---|---|---|
| `MimeTypes` | `MimeTypesInterface`, `MimeTypeGuesserInterface` | when first asked for; the container's own table, never `MimeTypes.get_default()` |
| `DefaultHtmlToTextConverter` | `HtmlToTextConverterInterface` | when first asked for |

Nothing is built at boot, and nothing is read from disk until the table is.

A `File` attachment names its type from `MimeTypes.get_default()`, the table the whole process
shares, not from the container's. To have attachments read the configured table, give each one
its `content_type`, or make the container's table the process's default yourself — a change to
every kernel and every caller in the process, which the bundle never makes for you:

```python
# app/boot/mime_default.py
from xtr_dependency_injection import Injected, on_boot
from xtr_mime import MimeTypes


@on_boot
async def share_the_mime_types(mime_types: Injected[MimeTypes]) -> None:
    MimeTypes.set_default(mime_types)
```

```python
# app/services/attachments.py
from xtr_dependency_injection import as_service
from xtr_mime import HtmlToTextConverterInterface, MimeTypesInterface


@as_service
class Attachments:
    def __init__(
        self, mime_types: MimeTypesInterface, converter: HtmlToTextConverterInterface
    ) -> None:
        self.mime_types = mime_types
        self.converter = converter
```

| `MimeConfig` field | Default | What it does |
|---|---|---|
| `extra_map` | `{}` | Extensions by MIME type, each without its leading dot, ranked before the standard table's |

```python
# app/config/packages/mime.py
from xtr_dependency_injection import configure
from xtr_mime.bundle import MimeConfig


@configure
def mime() -> MimeConfig:
    return MimeConfig(extra_map={"application/mbox": ["mbox"]})
```

**Guessers.** A service tagged `MIME_TYPE_GUESSER_TAG` (`"mime.mime_type_guesser"`) is asked by
the table before it answers from a file's extension — the highest `priority` first, then in the
order they were registered; `MagicMimeTypeGuesser`, inside every table already, is asked after
them. A class subclassing `MimeTypeGuesserInterface` is tagged without being told; one that only
has its methods joins once tagged:

```python
# app/services/upload_guesser.py
from typing_extensions import override
from xtr_dependency_injection import as_service
from xtr_mime import MimeTypeGuesserInterface


@as_service
class UploadGuesser(MimeTypeGuesserInterface):
    @override
    def is_guesser_supported(self) -> bool:
        return True

    @override
    def guess_mime_type(self, path: str) -> str | None:
        return "application/x-upload" if path.endswith(".upl") else None
```

A bundle tags one with a priority with
`services.set(UploadGuesser).add_tag(MIME_TYPE_GUESSER_TAG, priority=10)`. A tagged service that
is not a guesser fails the table when it is built, with `LogicError`; a priority that is not an
integer fails the build.

## Errors

Every error derives from `MimeError`, importable from `xtr_mime` and `xtr_mime.exception`.

| Error | Raised when |
|---|---|
| `MimeError` | The base: catch it to catch them all |
| `LogicError` | The library was used in a way that cannot work — an email with no sender or body, an extra not installed, a check on a message that cannot have what it asks about, a tagged service that is not a guesser. Also a `RuntimeError` |
| `MimeRuntimeError` | Something outside the code failed — an S/MIME certificate or key file missing or unreadable, libmagic failing on a file, the `ed25519-sha256` DKIM algorithm asked for. Also a `RuntimeError` |
| `InvalidArgumentError` | A value cannot be used — a missing or unreadable attachment, DKIM key file or file to guess the type of, an unknown charset or DKIM algorithm, a key that does not open, an S/MIME cipher cryptography cannot use, an extra map the table cannot read. Also a `ValueError` |
| `RfcComplianceError` | A value breaks the mail standards — an address that is not one, a domain with no ASCII form, a header line over 998 octets. An `InvalidArgumentError` |

## Known limitations

- **An email is rendered whole before its first chunk.** `to_iterable()` yields the message in
  pieces, but only once all of it is in memory: Python's email package writes a message from
  its whole tree, and an attachment's file is read whole into that tree. An email takes about
  its rendered size in memory while it is sent, however large its attachments.
- **Header bytes are the email package's.** It picks quoted-printable or base64 for an encoded
  word, writes it in lower case (`=?utf-8?q?...?=`) and folds where it chooses. Compare a header
  decoded, never as bytes.
- **A long ASCII word in a text header is written as it is.** A word too long for one line —
  a `List-Unsubscribe` URL — goes on a line of its own, unencoded, so it stays readable; a line
  longer than 998 octets is refused with `RfcComplianceError`.
- **Folding a long non-ASCII header takes time with its length.** About a second for a
  20,000-character subject on a laptop. Cap the length of what users type into a header.
- **A header parameter name is at most 40 characters.** A longer one is refused with
  `RfcComplianceError`: when its value has to be cut into RFC 2231 sections, the name may leave
  no room for them on a line.
- **A file's type comes from the built-in table.** `MimeTypes` reads the standard library's
  built-in table, never the host's `mime.types` files, so a message is the same on every
  machine. Content sniffing needs libmagic, which no wheel ships; without it
  `MagicMimeTypeGuesser` declines and the extension decides.
- **A form field's name is escaped as browsers do.** `FormDataPart` writes a name or filename as
  raw UTF-8 with `"`, CR and LF escaped, never in RFC 2231 form.
- **DKIM signs with `rsa-sha256` only.** `ed25519-sha256` is refused with `MimeRuntimeError`.
  There is no expiry (`x=`) and no cap on the body length signed; `body_show_length` only writes
  `l=` with the whole body's length. The signature's `t=` is read from the system clock by
  dkimpy, so a `MockClock` does not freeze it.
- **A DKIM-signed message turns back into an email from the parts it was signed from.**
  `MessageConverter` reads the text, HTML and attachments of the parts the signature was made
  over, not the bytes signed. A body read from a stream that cannot seek back was read when
  signing and comes out empty; attach bytes, a `File` or a seekable stream to a message you sign
  and hand to a provider's API. A body signed or encrypted with S/MIME is refused.
- **A DKIM or S/MIME passphrase is for an encrypted key only.** `DkimSigner` and `SMimeSigner`
  refuse a passphrase given with a key that is not encrypted (`InvalidArgumentError`), as
  cryptography, which opens the key, refuses it; pass an empty passphrase for such a key.
- **S/MIME signatures are detached, and encryption is AES-CBC for RSA keys.** `SMimeSigner`
  writes `multipart/signed` only — cryptography writes no opaque S/MIME signature — with an
  RSA key of at least 1024 bits or an EC key, and a SHA-2 digest; a certificate for RSA-PSS
  is refused, as cryptography signs with PKCS #1 v1.5 only. `SMimeEncrypter` encrypts with
  `aes-128-cbc` or `aes-256-cbc` (the default) for certificates holding an RSA key; the RC2,
  DES, 3DES and `aes-192-cbc` ciphers are refused with `InvalidArgumentError`.
- **The text made from an HTML body is written for reading, not the markup minus its tags.**
  On purpose, `DefaultHtmlToTextConverter` decodes character references, drops `<script>` —
  as it drops the head and `<style>` — with what it holds, collapses whitespace, and trims every
  line and the whole text, so a `<pre>` block loses its indentation. Lines break where the
  markup's own lines do, not at its elements: `<p>One</p><p>Two</p>` on one line reads `OneTwo`.
  Where the text must keep the body's characters as written, use a converter of your own
  implementing `HtmlToTextConverterInterface`.
- **Untrusted HTML needs an interpreter with the 2025 `html.parser` fixes.** The converter reads
  HTML with the standard library's parser, which before CPython 3.11.14, 3.12.12 and 3.13.6
  takes time growing with the square of the input on markup left unclosed, and loses the text
  after a `<script>` or `<style>` that is never closed. Convert HTML you do not write on one of
  those releases or a later one; every 3.14 release has the fixes.
- **The configured extra map is the container's alone.** `MimeConfig.extra_map` shapes the
  container's `MimeTypes` service; a `File` attachment reads `MimeTypes.get_default()`, which
  the bundle leaves as it is. Pass a `content_type`, or set the default yourself as
  [Kernel / bundle](#kernel--bundle) shows — process-wide, last kernel to set it wins.

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-mime`; run the commands below from there. The `python-xtr-mime` repository is a
read-only copy, so send issues and pull requests to the monorepo.

```sh
uv sync
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
