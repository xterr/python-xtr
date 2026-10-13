"""The HTTP message contract, implemented: six classes and the factory that builds them.

A library that handles requests should depend on the contract alone. An
application has to pick something that *is* a request, and this is that
something: small, strict, and tied to no web framework.

What is here is one class per interface, and nothing besides:

- :class:`~xtr_http_message.request.Request` — a request going out: a method,
  a URI, headers and a body, with the ``Host`` header taken from the URI.
- :class:`~xtr_http_message.server_request.ServerRequest` — a request that
  arrived, with the environment parameters, the cookies, the query string
  parsed, the files that came with it, the parsed body and the attributes a
  handler annotates it with.
- :class:`~xtr_http_message.response.Response` — a status code, the reason
  phrase recommended for it, headers and a body.
- :class:`~xtr_http_message.stream.Stream` — a body, as a cursor over bytes
  behind an open binary file object.
- :class:`~xtr_http_message.uri.Uri` — a URI taken apart into components and
  put back together as text.
- :class:`~xtr_http_message.uploaded_file.UploadedFile` — one file that came
  in with a request, movable once.
- :class:`~xtr_http_message.factory.http_factory.HttpFactory` — all six
  factory interfaces behind one object.

```python
from xtr_http_message import Response, ServerRequest

request = ServerRequest("GET", "https://example.com/orders?page=2")
assert request.get_query_params() == {"page": "2"}

response = Response(201, {"content-type": "application/json"}, b'{"id": 7}')
assert response.get_reason_phrase() == "Created"
```

Every message is immutable: a ``with_*`` method leaves the instance it was
called on alone and returns one carrying the change — and hands the same
instance back when the change would change nothing. A stream is the one thing
that is not: reading, writing and seeking move its cursor in place. Its
payload is bytes throughout, so ``await stream.get_contents()`` is how the
whole of a body is read; there is no encoding to guess at.

Bridging a message to the web framework an application runs on belongs with
that framework's integration, not here.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .exception import (
    HttpMessageError,
    InvalidArgumentError,
    StreamError,
    UploadedFileError,
)
from .factory import HttpFactory
from .request import Request
from .response import Response
from .server_request import ServerRequest
from .stream import Stream
from .uploaded_file import UploadedFile
from .uri import Uri

try:
    __version__ = version("xtr-http-message")
except PackageNotFoundError:  # pragma: no cover
    # Running from a source tree or a vendored copy, with no installed
    # metadata to read. Having no version is better than refusing to import.
    __version__ = "0+unknown"

__all__ = [
    "HttpFactory",
    "HttpMessageError",
    "InvalidArgumentError",
    "Request",
    "Response",
    "ServerRequest",
    "Stream",
    "StreamError",
    "UploadedFile",
    "UploadedFileError",
    "Uri",
    "__version__",
]
