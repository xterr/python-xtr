<div align="center">

# xtr-mime

**Build email messages — addresses, headers, text and HTML bodies, attachments and inline images — rendered to standard MIME by Python's own email package, signed with DKIM or S/MIME when asked.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

Coming: the package is being built; this page grows with it.

## Install

```sh
uv add xtr-mime
```

## Quick start

Coming with the message classes.

## Use in an application

Coming with the bundle.

## Kernel / bundle

Coming with the bundle.

## Errors

Coming with the package's errors.

## Known limitations

- **An email is rendered whole before its first chunk.** `to_iterable()` yields the message in
  pieces, but only once all of it is in memory: Python's email package writes a message from
  its whole tree, and an attachment's file is read whole into that tree. An email takes about
  its rendered size in memory while it is sent, however large its attachments.
- **A header parameter name is at most 40 characters.** A longer one is refused with
  `RfcComplianceError`: when its value has to be cut into RFC 2231 sections, the name may leave
  no room for them on a line.
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
  line and the whole text, so a `<pre>` block loses its indentation. Where the text must keep
  the body's characters as written, use a converter of your own implementing
  `HtmlToTextConverterInterface`.
- **Untrusted HTML needs an interpreter with the 2025 `html.parser` fixes.** The converter reads
  HTML with the standard library's parser, which before CPython 3.11.14, 3.12.12 and 3.13.6
  takes time growing with the square of the input on markup left unclosed, and loses the text
  after a `<script>` or `<style>` that is never closed. Convert HTML you do not write on one of
  those releases or a later one; every 3.14 release has the fixes.

## Development

```sh
cd packages/xtr-mime
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
