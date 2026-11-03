# What to watch for

The whole list, with what to do instead, is the README's *Known limitations*. These are the ones
that bite while writing code.

## DSNs

- **`smtp://host` with no port reaches 465 under implicit TLS** — every host but the literal
  `localhost`, so `smtp://127.0.0.1` and `smtp://[::1]` try TLS on 465 rather than plain SMTP on
  25. Write the port.
- **A sendmail `command` is not run through a shell.** It is split on spaces, honouring quotes,
  and handed to the operating system: `$VAR`, `~`, `*`, `|`, `&&` and redirection mean nothing,
  and the program is looked up as written.
- **`sendmail://default` uses `-bs`**, an SMTP session over the program's streams, which
  OpenSMTPD's `sendmail` does not implement. Use `?command=/usr/sbin/sendmail%20-t` there.
- **The 60-second child timeout is not a DSN option.** Only `SendmailTransport.set_timeout()`
  changes it.
- **A group takes neither a rate limiter nor `max_per_second`.** An option after a group's `)` is
  read as `retry_period` alone, so anything else is `The mailer DSN has some garbage at the end.`
  Pace each member's own DSN with `max_per_second`, or cap a single transport with
  `TransportConfig(dsn, rate_limiter=...)`.

## Lifetimes

- **A transport dropped without `stop()` keeps its socket**, and a finished `-bs` session keeps
  its sendmail child, until `stop()` or the end of the event loop. Nothing closes either on
  garbage collection. The bundle closes its transports when the container closes.
- **A stalled SMTP server holds shutdown up to the `timeout`** — 60 seconds by default — and
  `stop()` also waits for a send in flight. Several transports are stopped one after another.

## The queue

- **An email is queued only when `SendEmailMessage` is routed** — by its class, a base, or
  `"*"`. There is no `message_bus` option. A route under its wire name is not a route; an
  unrouted email is sent in-process, never dropped.
- **The limits are read limits, and the serializer reads every email back before handing it
  over**, so an oversized one never reaches the broker: `mailer.send` raises xtr-messenger's
  `MessageEncodingFailedError` naming the limit, and a message tampered with on the broker is
  refused in the worker with a `MessageDecodingFailedError`. Neither is a `MailerError`. Per
  message or part: 512 headers, 64 KiB of header text, 8 KiB per value, 1000 list entries, 64
  parameters. Per email: 2048 headers, 192 KiB of header text, 2000 addresses (Bcc counted),
  16 KiB of display-name text, 1024 non-ASCII name words, 16 KiB of non-ASCII text per value and
  32 KiB per email, 256 parts, 100 attachments, parts nested 32 deep. Per piece: a file name and
  a content type 256 characters, a header name 1 to 256 printable ASCII, a display name 256, a
  charset and a language 64, an address 320, and a template's variables plain JSON.
- **Attachments travel as content**, paths and streams included — a 10 MB attachment is 10 MB on
  the broker. A stream that cannot seek back, on an email also signed, arrives empty.
- **An envelope read from the headers is fixed at queue time**; a listener in the worker changing
  `To`, `Cc` or `Bcc` does not change where the mail goes.
- **Only this library's own classes travel.** An application subclass of `Email`, a header or a
  part is refused as the email is written, with a `MessageEncodingFailedError` whose reason names
  the class: `An email of class "MyEmail" cannot be queued.`
- **`X-Bus-Transport` is removed from the event's copy only.** The queued email keeps it, so the
  worker's SMTP DATA carries it; the caller's email keeps it too, and an unrouted email carries
  it to the mail server in-process. A server ignores it.

## S/MIME

- **Encryption shows who every recipient is**: each certificate's issuer and serial in clear, so
  a `Bcc` identity is visible to `To`, `Cc` and every relay.
- **`fail` refuses before logging; `encrypt` and `skip` log.** `encrypt` still sends mail the
  recipient cannot read; `skip` drops the address from the envelope but leaves it in `To` or
  `Cc`.
- **Lookup is exact** — no case, Unicode or IDN normalisation — and certificate files are read on
  the event loop, once per email.

## Elsewhere

- **An email renders whole in memory**, attachments included.
- **CPython 3.14.0's header folder can loop forever** on some whitespace-heavy subjects. Run a
  current patch release.
- **`EnvelopeListener` and `MessageLoggerListener` share priority -255**, so a recorded email may
  show the envelope before or after the override.
