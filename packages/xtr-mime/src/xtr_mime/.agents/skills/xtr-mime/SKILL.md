---
name: xtr-mime
description: How to build and render email messages with xtr-mime — an Email builder over Python's email package with checked addresses, typed headers, attachments, inline images, a text alternative made from HTML, DKIM and S/MIME signing, MIME type guessing and test assertions. Use when code must put together an email to send or store, attach a file or embed an image referenced by cid, sign a message with DKIM or sign and encrypt it with S/MIME, turn an HTML body into text, guess a file's MIME type, assert on an email in a test, or add MimeBundle to an application on xtr-dependency-injection.
---

# xtr-mime

An `Email` is a typed model of a message; Python's `email` package writes every byte of it,
header encoding and folding included. Nothing from the `email` package appears in the API.

## Quick reference

- Build: `Email().from_(...).to(...).subject(...).text(...).html(...)` — `from_` because `from`
  is a keyword; getters are `get_from()`, `get_to()`, …; `add_to` / `add_cc` append.
- Addresses: a string, or `Address("ana@example.com", "Ana")`. Bad ones raise
  `RfcComplianceError` when built.
- Render: `email.to_string()` (CRLF) or `email.to_iterable()` (bytes, in pieces). Rendering adds
  `Date`, `Message-ID`, `MIME-Version`; `ensure_validity()` checks author, recipient and body.
- Files: `attach_from_path(path)`, `attach(content, name, content_type)`,
  `embed_from_path(path)` / `embed(...)` for an image the HTML shows as `cid:<name>`.
- Signing, from `xtr_mime`: `DkimSigner` + `DkimOptions` (extra `dkim`), `SMimeSigner`,
  `SMimeEncrypter` (extra `smime`). Each returns a new `Message`; sign last.
- Text from HTML: `DefaultHtmlToTextConverter().convert(html, charset)`.
- Types: `MimeTypes(extra_map)` — `get_extensions`, `get_mime_types`, `guess_mime_type`,
  `register_guesser`; `MagicMimeTypeGuesser` needs extra `magic` and libmagic.
- Tests: `xtr_mime.testing` — `assert_email_*`, no test framework imported.
- Errors derive from `MimeError` — [references/limitations.md](references/limitations.md) for
  what the package does not do.

## Build and render an email

```python
from xtr_mime import Address, Email

email = (
    Email()
    .from_(Address("shop@example.com", "Example Shop"))
    .to("ana@example.com")
    .subject("Invoice A-17")
    .text("Your invoice is attached.")
    .html('<p><img src="cid:logo.png"> Your invoice is attached.</p>')
    .attach_from_path("invoice.pdf")
    .embed_from_path("logo.png")
)

email.ensure_validity()
wire = email.to_string()
assert "Content-Type: multipart/mixed;" in wire
```

A file is read when the email renders, typed by its extension unless `content_type` is given.
The embedded part gets a `Content-ID` and the HTML's `cid:logo.png` is rewritten to it.

## Sign and encrypt

```python
from pathlib import Path

from xtr_mime import DkimSigner, SMimeEncrypter, SMimeSigner

smime_signed = SMimeSigner("signer.crt", "signer.key").sign(email)
encrypted = SMimeEncrypter("recipient.crt").encrypt(smime_signed)
dkim_signed = DkimSigner(Path("dkim.pem"), "example.com", "mail").sign(encrypted)

assert dkim_signed.to_string().startswith("DKIM-Signature: v=1; a=rsa-sha256;")
```

Keys and certificates are opened when the signer is built, so a bad one fails there. DKIM is
`rsa-sha256` only; S/MIME signatures are detached and encryption is AES-CBC.

## Text from HTML

```python
from xtr_mime import DefaultHtmlToTextConverter

html = "<h1>Hi</h1>\n<p>A&nbsp;b</p><script>track()</script>"
assert DefaultHtmlToTextConverter().convert(html, "utf-8") == "Hi\nA b"
```

Scripts, styles and the head are dropped, references decoded, whitespace collapsed; lines break
only where the markup's lines do.

## Testing

- Build real emails; there is nothing to mock. Rendering reaches no network; an attached file
  is read when the email renders.
- Assert with `xtr_mime.testing`, which says what was expected and found:

  ```python
  from xtr_mime import Email
  from xtr_mime.testing import assert_email_header_same, assert_email_text_body_contains

  email = Email().from_("shop@example.com").to("ana@example.com").text("Hello Ana")

  assert_email_header_same(email, "To", "ana@example.com")
  assert_email_text_body_contains(email, "Ana")
  ```

- Compare rendered headers decoded, never as bytes: the encoded words are the `email` package's
  choice.
- Freeze `Date` with `Email(clock=MockClock(...))` from xtr-clock. A DKIM `t=` is not frozen;
  verify a signature instead of comparing it.
- With a kernel, `assert_zero_config(MimeBundle)` is the bundle's contract test.

## Use in an application

`uv run xtr-recipes recipes:sync` applies the recipe shipped with this package: it lists
`MimeBundle`. There is no config file, environment or ignore line to write.

1. **Install** — `uv add xtr-mime`; add `dkim`, `smime` or `magic` for what each brings.
2. **Activate** — `MimeBundle: {"all": True}` in `BUNDLES` in `<app>/config/bundles.py`,
   imported from `xtr_mime.bundle`.
3. **Brings along** — nothing.
4. **Configure** — optional: `MimeConfig(extra_map=...)` in a `<app>/config/packages/mime.py`
   `@configure` function adds extensions to the container's table only. A `File` attachment
   reads `MimeTypes.get_default()`, which the bundle never changes: pass `content_type`, or set
   the default yourself (process-wide) — [references/application.md](references/application.md).
5. **Environment** — nothing. **Ignore** — nothing.
6. **Use** — inject `MimeTypesInterface` (also `MimeTypeGuesserInterface`) and
   `HtmlToTextConverterInterface`. A class subclassing `MimeTypeGuesserInterface` is asked by the
   table without being told; tag others `MIME_TYPE_GUESSER_TAG` with a `priority` —
   [references/application.md](references/application.md).
7. **Check** — `debug:bundles` shows `mime` as `listed` and `active`.
8. **Remove** — `uv run xtr-recipes recipes:remove xtr-mime`, delete
   `<app>/config/packages/mime.py` if you wrote one.

## Errors

| Error | Raised when |
| --- | --- |
| `MimeError` | Base of them all |
| `LogicError` | Misuse — no author or body, extra missing, a check on raw bytes, a tagged service that is not a guesser. Also `RuntimeError` |
| `MimeRuntimeError` | The world failed — a file gone, libmagic broken, `ed25519-sha256` asked for. Also `RuntimeError` |
| `InvalidArgumentError` | A value cannot be used — charset, path, key, cipher, extra map. Also `ValueError` |
| `RfcComplianceError` | A value breaks the mail standards — an address, a domain, a line over 998 octets. An `InvalidArgumentError` |

## Do not

- Do not import from `email.*` to tweak a message; build it with the typed API.
- Do not assert on rendered header bytes or a whole rendered message: dates, ids and boundaries
  change every render.
- Do not change a message after signing it; sign last, DKIM after S/MIME.
- Do not put untrusted text of unbounded length in a header: folding long non-ASCII text is
  slow, and a line over 998 octets is refused.
- Do not convert untrusted HTML on an interpreter older than CPython 3.11.14, 3.12.12 or 3.13.6.
- Do not expect `MagicMimeTypeGuesser` to read content without libmagic installed; it declines
  and the extension decides.
- Do not register `MimeTypes` yourself in a container next to the bundle; configure
  `MimeConfig` and tag guessers.
