---
name: xtr-http-message
description: How to build and change requests, responses, streams, URIs and uploaded files with xtr-http-message. Use when code needs a concrete HTTP message rather than the interface - building a request or response in a test or a client, reading or writing a message body, taking a URI apart or putting one together, handling an uploaded file, or taking the factory that builds any of these. Also use when a message body reads as empty, a with_ method seems not to have changed anything, a header is refused, or a URI will not parse - a host, a port or a missing host that RFC 3986 and RFC 9110 refuse.
---

# xtr-http-message

The HTTP message contract, implemented. Six classes and one factory, no web framework. Code that
only *handles* messages should depend on `xtr-http-message-contracts` instead; this is what an
application, a test or a client installs to have something that actually is a message.

## Quick reference

- `Request(method, uri, headers=None, body=None, version="1.1")` — the `Host` header comes from
  the URI unless you pass one.
- `ServerRequest(method, uri, headers=None, body=None, version="1.1", server_params=None)` — the
  query parameters are read off the URI as it is built.
- `Response(status=200, headers=None, body=None, version="1.1", reason=None)` — `reason=None`
  takes the recommended phrase, `reason=""` leaves the response with none.
- `Stream.create(bytes | BinaryIO | StreamInterface)` — no `str`: a body is bytes.
- `Uri(text)` — read as RFC 3986 defines a URI reference;
  `UploadedFile(stream_or_file, size, error, client_filename=None, client_media_type=None)`.
- `HttpFactory()` is all six factory interfaces at once; it holds no state.
- **`bytes(stream)` is the body. `str(stream)` is not** — it is the object's repr, because a body
  may be binary and there is no encoding to guess at.
- Every `with_*` returns a new message and hands *the same one* back when nothing would change.
- `headers` maps a name to one value or to a sequence of them: `{"Accept": "text/html"}`,
  `{"X-Tag": ["a", "b"]}`.

## Build a request or a response

```python
from xtr_http_message import Request, Response

request = Request("POST", "https://example.com/orders", {"content-type": "text/plain"}, b"two")
assert request.get_header_line("host") == "example.com"
assert request.get_request_target() == "/orders"

response = Response(201, {"location": "/orders/7"})
assert response.get_reason_phrase() == "Created"
assert response.with_status(404).get_reason_phrase() == "Not Found"
```

Headers are matched without regard to case and reported in the case they were first given in.
A header the message does not carry reads as `[]` from `get_header` and `""` from
`get_header_line` — never an error.

## Read and write a body

```python
import asyncio

from xtr_http_message import Response


async def main() -> None:
    response = Response(200, None, b'{"id": 7}')

    assert await response.get_body().get_contents() == b'{"id": 7}'  # rewinds, then reads all

    body = response.get_body()
    await body.seek(0)
    assert await body.read(4) == b'{"id'


asyncio.run(main())
```

A message built with no body opens nothing until `get_body()` is asked for. A body is the one
thing here that is *not* immutable: writing to `get_body()` changes the message's body in place,
which is how an injected response is filled in.

```python
import asyncio

from xtr_http_message import Response


async def main() -> None:
    response = Response()
    _ = await response.get_body().write(b"hello")
    assert await response.get_body().get_contents() == b"hello"


asyncio.run(main())
```

## Take a URI apart and put one together

```python
from xtr_http_message import Uri

uri = Uri("https://user:pass@example.com:8080/path?q=abc#top")
assert (uri.get_host(), uri.get_port(), uri.get_query()) == ("example.com", 8080, "q=abc")

assert Uri("https://example.com:443").get_port() is None  # the scheme already says 443
assert str(Uri().with_path("/pa th")) == "/pa%20th"  # encoded once, never twice
assert Uri("/p%61th").get_path() == "/p%61th"  # already encoded, left alone
```

The splitting is RFC 3986's, done by `uritools`. Nothing is trimmed and no character is dropped:
what a path, a query string or a fragment may not carry as it is comes back per cent-encoded.
An authority that says something which is not an authority raises `InvalidArgumentError` naming
the whole string: a host that is neither an IPv6 address in two brackets nor a registered name of
unreserved characters, per cent escapes and sub-delimiters — a zone identifier between those
brackets, or a name in another script rather than its `xn--` form, is neither (§3.2.2); a port
outside sixteen bits (§3.2.3); a port with no host to hang off (§3.2); or an `http` or `https` URI
naming an authority with no host in it (RFC 9110 §4.2.1 and §4.2.2). `with_host` reads a host by
those same rules, since a request's `Host` header is written straight off it.

Anything else is read rather than refused, which is not the same as being a URI reference: a
string whose front is no scheme is read as a path, and §4.2 leaves a colon out of the first
segment of a relative-path reference, so `0:0` comes back as a path that would read as a scheme to
whoever resolved it.

```python
from xtr_http_message import Uri
from xtr_http_message.exception import InvalidArgumentError

assert Uri("http://h/a\nb").get_path() == "/a%0Ab"  # kept, as its escape
assert Uri("0:foo").get_scheme() == ""  # a scheme opens with a letter
assert Uri("http://u:p@ss@h/").get_user_info() == "u:p%40ss"  # encoded, so it reads back

local = Uri("file:///etc/hosts")  # a scheme other than http(s) may name no host
assert (local.get_host(), local.get_path()) == ("", "/etc/hosts")

refusal = ""
try:
    _ = Uri("http://exa mple.com")
except InvalidArgumentError as error:
    refusal = str(error)

assert refusal == 'Unable to parse URI: "http://exa mple.com"'
```

## Handle an uploaded file

```python
import asyncio

from xtr_http_message import Stream, UploadedFile
from xtr_http_message_contracts import UploadError


async def main() -> None:
    upload = UploadedFile(Stream.create(b"hello"), 5, UploadError.OK, "greeting.txt", "text/plain")
    assert await upload.get_stream().get_contents() == b"hello"

    await upload.move_to("greeting.txt")  # consumes it; a second move is refused


asyncio.run(main())
```

Given a path instead of a stream, the file is opened only when it is read, and `move_to` moves it
rather than copying it. Never trust `get_client_filename()`: a client chose it.

## Take the factory instead of the classes

```python
from xtr_http_message import HttpFactory
from xtr_http_message_contracts.factory import ResponseFactoryInterface


def deny(responses: ResponseFactoryInterface) -> None:
    response = responses.create_response(403)
    assert response.get_reason_phrase() == "Forbidden"


deny(HttpFactory())
```

`create_response(403)` fills in the recommended phrase; `create_response(403, "")` leaves the
response with no phrase at all. That is the difference between asking for the usual phrase and
asking for none.

## Where these classes do not belong: serving a request

Code that is **serving a request** never builds a response or a factory from this package. In
an application a response is either the injected `ResponseInterface` or one the injected
`ResponseFactoryInterface` made, and every response a `with_*` on one of those returns is the
integration's own — returned from the route as it is, with nothing to configure. `Response`
here knows no web framework, so one returned from a route is not something a framework can
send.

So: build these classes in a test, a worker or a console command, where no request is being
served. A message that arrived from such a place is sent by having the integration convert it —
for a FastAPI application, `xtr-http-kernel`'s `StarletteHttpFactory.create_response()`.

## Testing

Build real messages — there is nothing here worth faking. The classes do no I/O until a stream is
read, and a stream over bytes is held in memory.

```python
from xtr_http_message import ServerRequest


def test_the_handler_reads_the_page_it_was_asked_for() -> None:
    request = ServerRequest("GET", "/orders?page=2", {"accept": "application/json"})

    assert request.get_query_params() == {"page": "2"}
```

Use `tmp_path` for anything that touches disk, and close a stream your test opened from a path:
`Stream` closes the file object it was given when you close the stream, but not when the stream is
merely dropped.

```python
from pathlib import Path

from xtr_http_message import HttpFactory


def test_a_body_can_be_read_from_a_file(tmp_path: Path) -> None:
    path = tmp_path / "body.txt"
    _ = path.write_bytes(b"hello")

    stream = HttpFactory().create_stream_from_file(str(path))
    try:
        assert bytes(stream) == b"hello"
    finally:
        stream.close()
```

## Use in an application

1. **Install** — `uv add xtr-http-message`.
2. **Recipe** — there is none, and nothing for one to do: no bundle to list, no configuration
   file, no environment variable, no path to ignore.
3. **Activate** — nothing to activate. Build a class where you need one, or take `HttpFactory`
   as a dependency.
4. **Brings along** — `xtr-http-message-contracts`, `typing-extensions` and `uritools`. No web
   framework, no container.
5. **Configure** — nothing to configure.
6. **Environment** — nothing to set.
7. **Ignore** — nothing to ignore.
8. **Remove** — `uv remove xtr-http-message`.
9. **Check** — `python -c "from xtr_http_message import HttpFactory; print(HttpFactory().create_response(404).get_reason_phrase())"`
   prints `Not Found`.

Registering these classes on a container, and bridging a message to the web framework the
application runs on, belongs with that framework's integration — for a FastAPI application,
`xtr-http-kernel`. Read that package's *Use in an application* section for what it registers —
and the response rule above for what it asks you not to build.

## Errors

| Error | Is also | Raised when |
| --- | --- | --- |
| `HttpMessageError` | — | Never raised itself; the base the other three share |
| `InvalidArgumentError` | `ValueError` | A malformed header name or value, an out-of-range port, a status code outside 100-599, a URI that cannot be read, a parsed body that is a scalar |
| `StreamError` | `RuntimeError` | A detached, unseekable or unreadable stream; a file that will not open |
| `UploadedFileError` | `RuntimeError` | An upload that did not go through, or a file already moved |

Code written against the interfaces catches `ValueError` or `RuntimeError`; code that chose this
implementation can catch `HttpMessageError` and get only its failures.

## Do not

- Do not call `str(stream)` for a body — it is the object's repr. Use `bytes(stream)`.
- Do not pass a `str` to `Stream.create`; encode it first. A body is bytes, and guessing an
  encoding is how a binary body gets corrupted.
- Do not expect a `with_*` method to change the message it was called on: it returns a new one,
  and returns the same one when nothing would change. `request.with_header(...)` on its own does
  nothing — keep the result.
- Do not change a mapping or list one of the getters handed you and expect the message to follow:
  every one of them hands back a fresh copy.
- Do not import these classes in a library that only handles messages — depend on
  `xtr-http-message-contracts` and take the interface, so the application picks the
  implementation.
- Do not build a `Response` or an `HttpFactory` in code that is serving a request — a route, a
  listener, a per-request service. Take the registered `ResponseFactoryInterface`, or the
  injected `ResponseInterface`, and return what it gives you.
- Do not re-read `get_body().get_contents()` and wonder why it is empty the second time: it reads
  from the cursor onwards. `bytes(stream)` rewinds first.
- Do not call `move_to` twice on an uploaded file, or read it afterwards: moving consumes it.
- Do not expect a URI to be cleaned up for you: a blank, a tab or a control character is encoded
  rather than stripped, and a host carrying one is refused rather than patched — by `Uri(...)` and
  by `with_host` alike. Hand `Uri` a string a sender wrote, and catch `InvalidArgumentError`.
