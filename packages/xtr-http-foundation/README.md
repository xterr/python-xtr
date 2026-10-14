<div align="center">

# xtr-http-foundation

**One question each about a request that arrived, composed into one matcher — and the helpers that place an IP in a network.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="asyncio" src="https://img.shields.io/badge/asyncio-native-1f6feb">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

"Is this request one of mine?" is asked by a firewall, a webhook endpoint, a rate limiter and a
router, and each one answers it with its own tangle of `if`s over the method, the path and a
header or two. Written that way the answer is untestable on its own and subtly different
everywhere.

A matcher answers one such question, and a chain of them answers the whole of it. Alongside
them live the address helpers the questions about *who* sent a request are built on: whether an
IP falls in a network, and whether it is one only this network can reach.

## Install

```sh
uv add xtr-http-foundation
```

Requires Python 3.11+. The one runtime dependency beyond `typing-extensions` is
[xtr-http-message-contracts](../xtr-http-message-contracts), because a matcher reads a request
that arrived and nothing else; the address helpers are built on the standard library's
`ipaddress`.

## Quick start

A matcher answers one question, and `ChainRequestMatcher` answers the whole of it:

```python
from xtr_http_foundation import (
    ChainRequestMatcher,
    IsJsonRequestMatcher,
    MethodRequestMatcher,
    PathRequestMatcher,
)
from xtr_http_message import ServerRequest

ours = ChainRequestMatcher(
    [MethodRequestMatcher("POST"), PathRequestMatcher("^/webhook/"), IsJsonRequestMatcher()]
)

arrived = ServerRequest("POST", "/webhook/acme", {"Content-Type": "text/plain"}, b'{"id": 1}')

assert await ours.matches(arrived)
```

`matches()` is awaited on every matcher, including those that only read the head: a rule may be
about the body, and one matcher has to be swappable for another. The chain answers on the first
refusal, so a matcher that reads the body is never asked about a request an earlier one already
turned away — and a chain of nothing claims every request, because nothing constrains it.

## The matchers

| Matcher | Takes | Claims a request |
|---|---|---|
| `MethodRequestMatcher(methods)` | one method or several | whose method is one of them. The names are read in upper case; the request's own is compared as it arrived |
| `PathRequestMatcher(regexp)` | one expression | whose path matches it. Searched for rather than describing the whole path, so `/admin` claims anything under it and `^/admin/[0-9]+$` one shape of it |
| `HostRequestMatcher(regexp)` | one expression | whose host matches it, without regard to case: `\.example\.com$` is a subdomain rule, `^admin\.example\.com$` one host |
| `PortRequestMatcher(port)` | one port | asked of that port, the scheme's standard one counting where the URI is silent |
| `SchemeRequestMatcher(schemes)` | one scheme or several | made over one of them — `SchemeRequestMatcher("https")` is how a credential is kept off the clear |
| `HeaderRequestMatcher(headers)` | header names | carrying every one of them, whatever each holds. Names match the way HTTP matches them |
| `QueryParameterRequestMatcher(parameters)` | parameter names | whose query *opens* with them, in that order; further parameters after them are fine |
| `IpsRequestMatcher(ips)` | addresses or CIDR networks | that came from one of them |
| `AttributesRequestMatcher(regexps)` | each attribute name mapped to an expression | whose every named attribute matches its own |
| `IsJsonRequestMatcher()` | nothing | whose body reads as JSON |
| `ChainRequestMatcher(matchers)` | matchers | every one of them claims |

Wherever a matcher takes several names, one string is as good as a sequence and any of them may
itself hold a comma-separated list — `MethodRequestMatcher("POST,PUT")` is
`MethodRequestMatcher(["POST", "PUT"])`. A matcher naming nothing at all claims every request:
it constrains nothing.

Expressions are read when the matcher is built, so one that does not read as an expression is
`InvalidArgumentError` there rather than on the first request. They are *searched for* in the
value, never anchored for you.

Three of them are worth a sentence of their own.

- **`IsJsonRequestMatcher` reads the body, not the `Content-Type` header.** A sender that
  announces nothing still sent JSON, and one that announces JSON and sent something else did
  not. Any JSON value counts — an object, an array, a number, a string — so this is the rule for
  "a body worth decoding" rather than for a shape. The body is read from its first byte, a
  stream another matcher already read being rewound first, so the order of a chain changes
  nothing; a body nobody can read is simply not claimed.
- **`IpsRequestMatcher` reads the address the server accepted the connection from**, reported
  among the request's server parameters under `client`. A request that travelled through a proxy
  therefore comes from the proxy: a rule about the original caller belongs where the forwarded
  headers are trusted and resolved.

  ```python
  from xtr_http_foundation import IpsRequestMatcher
  from xtr_http_message import ServerRequest

  internal = IpsRequestMatcher("10.0.0.0/8,192.168.1.7")
  arrived = ServerRequest("GET", "/metrics", server_params={"client": ("10.1.2.3", 51234)})

  assert await internal.matches(arrived)
  ```

- **`PathRequestMatcher` matches the path the application itself sees**, free of per cent
  escapes: an application mounted under a path is reached at that path plus its own, the mount
  is reported as the `root_path` server parameter, and a rule is written about the application's
  own path — so moving the mount rewrites no matcher. `/admin/fo o` therefore matches
  `/admin/fo%20o`, and nothing in the expression is a path parameter: `^/{_locale}/login$`
  matches a path holding those very braces.

`AttributesRequestMatcher` is the one that asks about a finding rather than about the request as
it arrived — the named parameters a path matched, the user an authorization header resolved to:

```python
from xtr_http_foundation import AttributesRequestMatcher
from xtr_http_message import ServerRequest

owners = AttributesRequestMatcher({"role": "^owner$"})
arrived = ServerRequest("GET", "/orders").with_attribute("role", "owner")

assert await owners.matches(arrived)
```

An attribute the request does not carry, or carries as something that is not text, is never
claimed: there is nothing to match an expression against.

## Writing one

`RequestMatcherInterface` is a `@runtime_checkable` `Protocol` with one member, so a rule of
your own needs no base class:

```python
from typing import final

from typing_extensions import override
from xtr_http_foundation import RequestMatcherInterface
from xtr_http_message_contracts import ServerRequestInterface


@final
class SignedRequestMatcher(RequestMatcherInterface):
    __slots__ = ()

    @override
    async def matches(self, request: ServerRequestInterface) -> bool:
        return request.has_header("Webhook-Signature")
```

## Addresses

`IpUtils` is a namespace rather than something to build: every answer is a function of its
arguments.

```python
from xtr_http_foundation import IpUtils

IpUtils.check_ip("10.1.2.3", ["192.168.0.0/16", "10.0.0.0/8"])  # True
IpUtils.check_ip4("10.1.2.3", "10.0.0.0/8")  # True
IpUtils.check_ip6("::1", "::1/128")  # True
IpUtils.is_private_ip("10.1.2.3")  # True
IpUtils.anonymize("192.168.1.42")  # "192.168.1.0"
IpUtils.anonymize("2001:db8::1")  # "2001:db8::"
```

- `check_ip(request_ip, ips)` takes a single address, a network in CIDR notation, or several of
  either, and picks the IPv4 or the IPv6 check by how the address is written.
- **Text that is no address is no error for the checks**: they answer about a request from a
  stranger, whose address is theirs to misspell, and an address nobody can read is one no
  network holds. A network written wrongly is read as no network at all rather than as a wider
  one: `" 8"`, `"+8"` and `"8.5"` name no prefix length, and an IPv6 zone — the `%eth0` of
  `fe80::1%eth0`, which names an interface of whichever host reads it — is refused rather than
  quietly dropped.
- `is_private_ip(ip)` is the one that *refuses* unreadable text, with `InvalidArgumentError`:
  its caller is asking whether an address may be reached out to, and text nobody can read is not
  an address that failed the question. It places the address in `IpUtils.PRIVATE_SUBNETS` —
  loopback, private use, link-local, carrier-grade NAT, unique-local, multicast, reserved,
  unspecified, the documentation and benchmarking ranges, and the forms an IPv6 address writes
  an IPv4 one in. That tuple is what
  [xtr-http-client](../xtr-http-client)'s `NoPrivateNetworkHttpClient` guards by default.
- `anonymize(ip, v4_bytes=1, v6_bytes=8)` zeroes the last bytes, so what is left no longer names
  one machine — for a log or a counter that must not keep an address. It gives the address back
  as it arrived, bracketed if it was and dotted where it carries an IPv4 one, and never gives a
  zone back: that names an interface, which is as much a trace of who was asked as the bytes
  just dropped. Asking for fewer than no bytes, or for more than the address has, is
  `InvalidArgumentError`.

## Errors

Everything derives from `HttpFoundationError`. There is one: `InvalidArgumentError`, also a
`ValueError`, raised for an expression that does not read as one, and by `is_private_ip` and
`anonymize` for text that is no address.

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-http-foundation`; run the commands below from there. The
`python-xtr-http-foundation` repository is a read-only copy, so send issues and pull requests
to the monorepo.

```sh
uv sync --all-extras
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
