# Signature formats, byte for byte

What each format signs, what it puts on the wire, and how to move between them. Both ends of a
webhook must have made the same choice, which is why `SignatureFormat` is taken by the sender's
configurators and by the receiver's parser alike.

`SignatureFormat` is a string enum, so the members *are* their strings: a configuration file, an
option mapping or an environment variable carries `"legacy"`, `"standard"` or `"transitional"`
and is understood with no conversion step. `SignatureFormat.parse(value)` is the single door for
anything arriving from outside, and raises `InvalidArgumentError` with
`"<value>" is not a signature format; use "legacy", "standard" or "transitional".`

## Legacy

The historical format, and the default, so an existing pair of endpoints keeps working.

Signed bytes are the three run together with nothing between them:

```
event.name + event.id + body
```

The header value names the digest, so a receiver knows what to recompute:

```
Webhook-Signature: sha256=<hexdigest>
```

Recomputing it by hand:

```python
import hmac

expected = (
    "sha256="
    + hmac.new(
        secret.encode(), event_name.encode() + event_id.encode() + body, "sha256"
    ).hexdigest()
)
```

A full delivery:

```http
POST /hook HTTP/1.1
Content-Type: application/json
Webhook-Id: evt_1
Webhook-Timestamp: 1767225600
Webhook-Event: order.paid
Webhook-Signature: sha256=0f8c...

{"total":4200}
```

`signing_algorithm` picks the digest; anything `hashlib` cannot make is refused where it is
configured rather than at the first delivery. The event name is in `Webhook-Event`, which this
signature covers, so the receiver may act on it.

**No timestamp is signed.** `Webhook-Timestamp` is sent, but nothing covers it, so refusing on
it would mean trusting a value an attacker sets. There is no replay protection in this format.

## Standard Webhooks

The [standardwebhooks.com](https://www.standardwebhooks.com/) scheme. Always HMAC-SHA256 — the
scheme fixes the digest, so `signing_algorithm` does not apply to it.

Signed bytes, with the id and the timestamp dot-separated ahead of the body:

```
f"{message_id}.{timestamp}.".encode() + body
```

The header value is the version marker and the base64 of the digest:

```
Webhook-Signature: v1,<base64>
```

A full delivery. There is no `Webhook-Event` header at all, because this signature covers no
header, so a name sent as one is a value the receiver cannot trust. The name goes in the
payload's `type` key instead:

```http
POST /hook HTTP/1.1
Content-Type: application/json
Webhook-Id: evt_1
Webhook-Timestamp: 1767225600
Webhook-Signature: v1,dGhlLXNpZ25hdHVyZQ==

{"total":4200,"type":"order.paid"}
```

A payload that already carries `type` keeps what it says: the application knows its own events
better than their source name does. The payload is copied before the key is added, so sending a
webhook never edits the dict the caller is still holding. A payload whose `type` is missing or
not a string names no event and is refused with
`The payload is missing the "type" key holding the event name.`

### The secret's encoding

The scheme writes a secret as base64 behind a `whsec_` prefix, so the key need not be text:

- `whsec_<base64>` — the key is those bytes, decoded.
- Anything else, including a `whsec_` prefix over something that is not valid base64, is its own
  key. A receiver configured with a plain string must keep working, and a secret that happens to
  start with those six characters is not a mistake to raise over.
- A prefix over nothing decodes to an empty key, which is no secret at all, so that falls back to
  the secret itself too.

### The replay window

Because the timestamp is signed, it can be held to a window around now: `timestamp_tolerance`,
300 seconds by default, either side. Zero or less turns the bound off, for when clocks that
cannot be kept close enough matter more than a replayed capture.

The check runs only after a Standard Webhooks entry verified, which is when the timestamp is
known to be the sender's rather than an attacker's. A timestamp that does not read as an integer
is refused as well — a value that cannot be bounded is not accepted on faith. The refusal is
`The "Webhook-Timestamp" HTTP request header is outside the accepted window.`

## Transitional

Both signatures, space separated in one header, with the event name in both the header and the
payload:

```
Webhook-Signature: sha256=0f8c... v1,dGhlLXNpZ25hdHVyZQ==
```

A receiver on this format accepts either entry, which is what lets the two ends migrate on
different days. Only the Standard Webhooks entry bounds replays, and a request carrying both is
tried Standard-first, so it is replay-bounded whatever order its entries arrive in.

### Migrating

Legacy to Standard, with nothing refused in between:

1. Set the **receiver** to `transitional`. It now accepts both, and still accepts everything the
   sender sends today.
2. Set the **sender** to `transitional`. Every delivery now carries both entries.
3. Set the **receiver** to `standard`. Legacy entries stop being accepted; the sender is still
   sending the Standard one too.
4. Set the **sender** to `standard`. The legacy entry stops being emitted, and the
   `Webhook-Event` header with it — so anything downstream reading that header must already read
   the payload's `type`.

Backwards is the same four steps read upwards.

## Rotating a secret

The signature header may carry several whitespace-separated entries, one per secret in play, and
**any one that verifies is enough**. So:

1. The sender signs with both the old and the new secret, sending both entries.
2. The receiver's configured secret is changed to the new one.
3. The sender drops the old secret.

Each expectation is computed once, before its loop, so the number of entries a request carries
does not drive the CPU cost of rejecting it, and every comparison is `hmac.compare_digest`.

## Header names

All four are configurable, on `WebhookConfig` and on each configurator and the parser:

| Option | Default | Read by |
| --- | --- | --- |
| `id_header_name` | `Webhook-Id` | both signatures |
| `timestamp_header_name` | `Webhook-Timestamp` | the Standard signature |
| `event_header_name` | `Webhook-Event` | the legacy signature |
| `signature_header_name` | `Webhook-Signature` | the entries themselves |

`HeadersConfigurator` writes the timestamp under the same name `HeaderSignatureConfigurator`
reads it back from, so changing one means changing both. The signer runs last; a format that
signs the timestamp, running before whatever wrote it, raises `LogicError` naming the header.

## Which headers must be present

`RequestParser` refuses a request missing a header its format needs, with
`Missing "<name>" HTTP request signature header.`

| Format | Required |
| --- | --- |
| `LEGACY` | signature, id, event |
| `STANDARD` | signature, id, timestamp |
| `TRANSITIONAL` | signature, id |

Under `TRANSITIONAL` only the two shared headers are required, because which entry will verify
is not known yet; whichever scheme's own headers are absent simply cannot be the one that
authenticates the request.
