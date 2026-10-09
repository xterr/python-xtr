"""The HTTP message contract: what code that handles requests depends on, and nothing more.

A library that reads a request or fills in a response should not decide which
class is one. It takes a :class:`ServerRequestInterface` and a
:class:`ResponseInterface`, or the factory that makes them, and leaves the
choice of implementation to the application — so two libraries written against
this contract pass messages to each other without either knowing what the
other installed.

What is here is only what appears in that contract:

- :class:`MessageInterface` — the protocol version, headers and body every
  message has.
- :class:`RequestInterface` / :class:`ServerRequestInterface` — a request
  going out, and one that arrived with everything the server learned
  alongside it.
- :class:`ResponseInterface` — a status code, a reason phrase, and a message.
- :class:`StreamInterface` — the body, as a cursor over bytes.
- :class:`UriInterface` — a URI taken apart into its components.
- :class:`UploadedFileInterface` and :class:`UploadError` — a file that came
  in with a request, and how its upload went.
- The six factories, also under ``xtr_http_message_contracts.factory``, for
  building any of the above without naming a class.

Every message is immutable: a ``with_*`` method leaves the instance it was
called on alone and returns one carrying the change.

```python
from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface


def whoami(request: ServerRequestInterface, response: ResponseInterface) -> ResponseInterface:
    _ = response.get_body().write(request.get_header_line("user-agent").encode())
    return response.with_header("content-type", "text/plain")
```

An implementation builds on these types rather than redefining them, so a
container can register one under an interface and a library that never
imported it receives it. Bridging a message to the web framework an
application runs on belongs with that framework's integration, not here.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .factory import (
    RequestFactoryInterface,
    ResponseFactoryInterface,
    ServerRequestFactoryInterface,
    StreamFactoryInterface,
    UploadedFileFactoryInterface,
    UriFactoryInterface,
)
from .message_interface import MessageInterface
from .request_interface import RequestInterface
from .response_interface import ResponseInterface
from .server_request_interface import ServerRequestInterface
from .stream_interface import StreamInterface
from .upload_error import UploadError
from .uploaded_file_interface import UploadedFileInterface
from .uri_interface import UriInterface

try:
    __version__ = version("xtr-http-message-contracts")
except PackageNotFoundError:  # pragma: no cover
    # Running from a source tree or a vendored copy, with no installed
    # metadata to read. Having no version is better than refusing to import.
    __version__ = "0+unknown"

__all__ = [
    "MessageInterface",
    "RequestFactoryInterface",
    "RequestInterface",
    "ResponseFactoryInterface",
    "ResponseInterface",
    "ServerRequestFactoryInterface",
    "ServerRequestInterface",
    "StreamFactoryInterface",
    "StreamInterface",
    "UploadError",
    "UploadedFileFactoryInterface",
    "UploadedFileInterface",
    "UriFactoryInterface",
    "UriInterface",
    "__version__",
]
