---
name: xtr-http-foundation
description: How to say "is this request one of mine" with xtr-http-foundation — one matcher per question about a request that arrived (method, path, host, port, scheme, a header, a query parameter, an attribute, the address it came from, a JSON body, or whatever a callable reads), chained into one, plus the IpUtils helpers that place an IP in a network, the request-rate-limiter contracts that count a request under the limits its own content names, and the header values that set or clear a response cookie. Use when a firewall, webhook endpoint, rate limiter, router or middleware has to decide which requests it claims; when replacing a tangle of ifs over the method and path with something testable; when writing a request parser's matcher; when a login form or an endpoint must throttle requests by who sends them; when a response must set or clear a cookie; and when checking whether an address is inside a subnet, is reachable only from this network, or must be logged without identifying one machine.
---

# xtr-http-foundation

A matcher answers one question about a request that arrived, and a chain of them answers the
whole of it — so what a piece of code claims is a value it can be handed rather than a
condition written into it. Beside them live the address helpers those questions are built on,
the contracts that count a request against the limits it names, and the header values that set
or clear a response cookie.

## Quick reference

- Every matcher is a `RequestMatcherInterface` with one member:
  `await matcher.matches(request)` → `bool`. The request is a `ServerRequestInterface`.
- `matches()` is awaited even on a matcher that only reads the head, so one can be swapped for
  another.
- `ChainRequestMatcher([...])` claims a request only when all of them do, answering on the
  first refusal. A chain of nothing claims everything.
- A matcher naming nothing claims everything. One string is as good as a sequence, and any
  entry may hold a comma-separated list.
- Expressions are compiled when the matcher is built — a bad one is `InvalidArgumentError`
  there — and are *searched for*, never anchored for you.
- `IpUtils.check_ip`, `check_ip4`, `check_ip6`, `is_private_ip`, `anonymize`,
  `IpUtils.PRIVATE_SUBNETS`. All static; there is nothing to build.
- The request rate limiters: `RequestRateLimiterInterface` (`await consume(request)` /
  `await reset(request)`), `PeekableRequestRateLimiterInterface` (+ `await peek(request)`),
  `AbstractRequestRateLimiter` (subclass it, implement `get_limiters(request)`). The answer is
  anything carrying `RequestRateLimitInterface`.
- `cookie_header_value(name, value, ...)` and `cleared_cookie_header_value(name, ...)` build
  `Set-Cookie` header values — place them with `response.with_header("Set-Cookie", ...)`. No
  response type comes with them.

## Claim the requests that are yours

```python
from xtr_http_foundation import (
    ChainRequestMatcher,
    IsJsonRequestMatcher,
    MethodRequestMatcher,
    PathRequestMatcher,
)

ours = ChainRequestMatcher(
    [MethodRequestMatcher("POST"), PathRequestMatcher("^/webhook/"), IsJsonRequestMatcher()]
)

if await ours.matches(request):
    ...
```

| Matcher | Takes | Claims a request |
| --- | --- | --- |
| `MethodRequestMatcher(methods)` | one method or several | whose method is one of them; names read in upper case, the request's compared as it arrived |
| `PathRequestMatcher(regexp)` | one expression | whose path matches it |
| `HostRequestMatcher(regexp)` | one expression | whose host matches it, without regard to case |
| `PortRequestMatcher(port)` | one port | asked of that port, the scheme's standard one counting where the URI is silent |
| `SchemeRequestMatcher(schemes)` | one scheme or several | made over one of them |
| `HeaderRequestMatcher(headers)` | header names | carrying every one, whatever each holds |
| `QueryParameterRequestMatcher(parameters)` | parameter names | whose query *opens* with them, in that order |
| `IpsRequestMatcher(ips)` | addresses or CIDR networks | that came from one of them |
| `AttributesRequestMatcher(regexps)` | attribute name → expression | whose every named attribute matches its own |
| `IsJsonRequestMatcher()` | nothing | whose body reads as JSON |
| `CallableRequestMatcher(decide)` | a callable reading the request | when the callable says so — the escape hatch where no matcher here expresses the claim |
| `ChainRequestMatcher(matchers)` | matchers | every one of them claims |

Three behave in a way worth knowing before you rely on them.

- **`IsJsonRequestMatcher` reads the body, not the `Content-Type` header.** A sender that
  announces nothing still sent JSON; one that announces JSON and sent something else did not.
  Any JSON value counts, so this is the rule for "a body worth decoding" rather than for a
  shape. The body is read from its first byte — a stream another matcher already read is
  rewound — so the order of a chain changes nothing, and a body that cannot be read is simply
  not claimed.
- **`IpsRequestMatcher` reads the address the server accepted the connection from**, which the
  request carries among its server parameters under `client`. A request through a proxy comes
  *from the proxy*; a rule about the original caller belongs where the forwarded headers are
  trusted and resolved.
- **`PathRequestMatcher` matches the path the application itself sees**, with the mount
  (`root_path` among the server parameters) removed and per cent escapes undone — so
  `/admin/fo o` matches `/admin/fo%20o`, and moving the mount rewrites no matcher. Nothing in
  the expression is a path parameter: `^/{_locale}/login$` matches those very braces.

```python
from xtr_http_foundation import AttributesRequestMatcher, HostRequestMatcher, IpsRequestMatcher

internal = IpsRequestMatcher("10.0.0.0/8,192.168.1.7")
subdomain = HostRequestMatcher(r"\.example\.com$")
owners = AttributesRequestMatcher({"role": "^owner$"})
```

An attribute the request does not carry, or carries as something that is not text, is never
claimed.

## Write a matcher

`RequestMatcherInterface` is a `@runtime_checkable` `Protocol`, so no base class is needed:

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

## Place an address

```python
from xtr_http_foundation import IpUtils

IpUtils.check_ip("10.1.2.3", ["192.168.0.0/16", "10.0.0.0/8"])  # True
IpUtils.check_ip4("10.1.2.3", "10.0.0.0/8")  # True
IpUtils.check_ip6("::1", "::1/128")  # True
IpUtils.is_private_ip("10.1.2.3")  # True
IpUtils.anonymize("192.168.1.42")  # "192.168.1.0"
IpUtils.anonymize("2001:db8::1")  # "2001:db8::"
```

- `check_ip` takes a single address, a CIDR network, or several of either, and picks the IPv4 or
  the IPv6 check by how the address is written.
- **The checks never raise over unreadable text**: they answer about a request from a stranger,
  and an address nobody can read is one no network holds. A network written wrongly is read as
  no network rather than as a wider one — `" 8"`, `"+8"`, `"8.5"` name no prefix length — and an
  IPv6 zone such as `fe80::1%eth0` is refused, since it names an interface of whichever host
  reads it.
- `is_private_ip` is the one that **does** raise `InvalidArgumentError` for text that is no
  address: its caller is asking whether an address may be reached out to. It places the address
  in `IpUtils.PRIVATE_SUBNETS` — loopback, private use, link-local, carrier-grade NAT,
  unique-local, multicast, reserved, unspecified, the documentation and benchmarking ranges, and
  the forms an IPv6 address writes an IPv4 one in.
- `anonymize(ip, v4_bytes=1, v6_bytes=8)` zeroes the last bytes and gives the address back as it
  arrived — bracketed if it was, dotted where it carries an IPv4 one, and never with its zone.
  Fewer than no bytes, or more than the address has, is `InvalidArgumentError`.

## Limit a request

```python
from typing import final

from typing_extensions import override
from xtr_http_foundation import AbstractRequestRateLimiter


@final
class PerAddressLimiter(AbstractRequestRateLimiter):
    def __init__(self, factory) -> None:
        self._factory = factory

    @override
    def get_limiters(self, request):
        address, _port = request.get_server_params().get("client", ("", 0))
        return [self._factory.create(address)]
```

- `await limiter.consume(request)` counts the request and answers with the strictest limit it
  counts under; `await limiter.peek(request)` reports the limit without counting (for counting
  only failures); `await limiter.reset(request)` forgets the hits.
- The answer carries `RequestRateLimitInterface` — `is_accepted()`, `remaining_tokens`,
  `retry_after`, `limit`, `reset_at` — so
  [xtr-rate-limiter](https://github.com/xterr/python-xtr/tree/main/packages/xtr-rate-limiter)'s
  `RateLimit` answers as-is, and its factories' limiters satisfy `RateLimiterInterface`
  without either package importing the other.
- A request counting under no limiter is unlimited: the answer is accepted, with nothing left
  to run out of.

## Set or clear a response cookie

```python
from datetime import UTC, datetime

from xtr_http_foundation import cleared_cookie_header_value, cookie_header_value

response = response.with_header(
    "Set-Cookie",
    cookie_header_value("session", token, expires=datetime(2035, 1, 1, tzinfo=UTC), secure=True),
)
response = response.with_header("Set-Cookie", cleared_cookie_header_value("session"))
```

- The value is per cent-encoded; `expires` writes both the `expires` date and the `Max-Age` a
  client counts down; `path` defaults to the whole site, `httponly` is on and `samesite` is
  `lax` by default.
- Clearing repeats the path and the domain the cookie was set with — a browser tells cookies
  apart by all three — and dates it a year behind.
- `__Secure-` and `__Host-` names must be built `secure=True`; `__Host-` also asks for no
  `domain` and the path `/`. A browser silently discards the cookie otherwise; the builder
  refuses it first.

## Testing

A matcher is a value, so a test hands it a request it built and asserts the one answer:

```python
import pytest
from xtr_http_foundation import IpsRequestMatcher, MethodRequestMatcher
from xtr_http_message import ServerRequest


@pytest.mark.anyio
async def test_it_claims_a_post_from_inside_the_network() -> None:
    matcher = IpsRequestMatcher("10.0.0.0/8")
    arrived = ServerRequest("POST", "/metrics", server_params={"client": ("10.1.2.3", 51234)})

    assert await matcher.matches(arrived)
    assert await MethodRequestMatcher("POST").matches(arrived)
```

- Build requests with `ServerRequest(method, uri, headers, body, version, server_params)` from
  [xtr-http-message](https://github.com/xterr/python-xtr/tree/main/packages/xtr-http-message)
  — a dev dependency here, since only tests build a request.
- Give `server_params={"client": (address, port)}` for `IpsRequestMatcher` and
  `server_params={"root_path": "/mounted"}` for `PathRequestMatcher`; without them each reads
  as nothing supplied.
- Set what `AttributesRequestMatcher` reads with `request.with_attribute(name, value)`.
- Pass the body as bytes for `IsJsonRequestMatcher`; nothing has to be rewound by hand.

## Use in an application

This package **ships no bundle and no recipe**: a matcher is a value built where the rule is
written, not a service to configure.

1. **Install** — `uv add xtr-http-foundation`. There are no extras.
2. **Activate** — nothing to do. Nothing is registered, so nothing is listed in `BUNDLES`.
3. **Configure** — nothing. Build the matchers where the rule belongs, usually in the class
   that asks the question.
4. **Environment** and **Ignore** — nothing.
5. **Check** — the test above: a matcher is testable on its own, which is the point of it.
6. **Remove** — `uv remove xtr-http-foundation`.

Packages that *do* wire these for you say so in their own sections: a
[xtr-webhook](https://github.com/xterr/python-xtr/tree/main/packages/xtr-webhook) parser
returns one from `get_request_matcher()`, and
[xtr-http-client](https://github.com/xterr/python-xtr/tree/main/packages/xtr-http-client)'s
`NoPrivateNetworkHttpClient` guards `IpUtils.PRIVATE_SUBNETS` by default.

## Errors

Everything derives from `HttpFoundationError`. There is one: `InvalidArgumentError`, also a
`ValueError`, raised for an expression that does not read as one, and by `is_private_ip` and
`anonymize` for text that is no address, and by the cookie builder for a name it cannot write,
a `samesite` that is none of the three, or a `path` or `domain` an attribute cannot carry.

## Do not

- Do not check `Content-Type` to decide whether a body is JSON — `IsJsonRequestMatcher` reads
  the body, which is the only thing that settles it.
- Do not trust `IpsRequestMatcher` for the original caller behind a proxy; resolve the forwarded
  headers first, where they are trusted.
- Do not expect an expression to be anchored: `PathRequestMatcher("/admin")` claims anything
  containing that path. Write `^/admin/` when that is the rule.
- Do not write path parameters into a `PathRequestMatcher` expression — `{id}` matches braces.
- Do not pass host names to `IpsRequestMatcher` or to the `IpUtils` checks: they place
  addresses, and a name would have to be resolved first.
- Do not call `matches()` without awaiting it — every matcher is async, including the ones that
  only read the head.
- Do not pass an empty matcher expecting it to refuse everything: a matcher naming nothing
  claims every request.
- Do not build a `Set-Cookie` value by hand: the encoding, the dual `expires`/`Max-Age`, and
  the prefix rules are what make a browser keep the cookie — `cookie_header_value` carries
  them.
