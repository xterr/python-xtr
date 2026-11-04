# What xtr-mime does not do

- **Streaming.** An email is rendered whole in memory before its first chunk, attachments
  included.
- **Byte-exact headers.** Encoded words, their case (`=?utf-8?q?...?=`) and folding are the
  `email` package's. A long ASCII word in a text header goes on a line of its own, unencoded; a
  line over 998 octets raises `RfcComplianceError`. A header parameter name is at most 40
  characters.
- **Fast folding of huge non-ASCII headers.** About a second per 20,000 characters: cap user
  input.
- **The host's `mime.types`.** Only the standard library's built-in table, plus `extra_map`.
- **RFC 2231 form fields.** `FormDataPart` escapes names as browsers do.
- **DKIM beyond `rsa-sha256`.** `ed25519-sha256` raises `MimeRuntimeError`; no `x=` expiry, no
  body length cap; `t=` comes from the system clock.
- **Opaque S/MIME or other ciphers.** Signatures are detached; encryption is `aes-128-cbc` or
  `aes-256-cbc` for RSA certificates. A passphrase is refused for a key that is not encrypted.
- **Faithful HTML text.** `DefaultHtmlToTextConverter` drops scripts, styles and the head,
  decodes references, collapses whitespace and trims; `<p>One</p><p>Two</p>` on one line reads
  `OneTwo`. Write a converter implementing `HtmlToTextConverterInterface` for anything else.
- **Old `html.parser`.** Before CPython 3.11.14, 3.12.12 and 3.13.6 unclosed markup is quadratic
  and an unclosed `<script>` hides the rest.
- **Attachments reading the configured table.** `MimeConfig.extra_map` shapes the container's
  table; a `File` attachment reads `MimeTypes.get_default()`, which the bundle never sets.
