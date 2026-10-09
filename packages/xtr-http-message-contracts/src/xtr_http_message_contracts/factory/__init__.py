"""The six factories, so that code which builds messages names no class.

A library that has to make a request, a response, a stream, a URI or an
uploaded file takes the matching factory and stays free of whichever
implementation the application installed:

```python
class Probe:
    def __init__(self, requests: RequestFactoryInterface) -> None:
        self._requests = requests

    def ping(self, url: str) -> RequestInterface:
        return self._requests.create_request("HEAD", url)
```

- :class:`RequestFactoryInterface` / :class:`ServerRequestFactoryInterface` —
  a request going out, and one that arrived.
- :class:`ResponseFactoryInterface` — a response.
- :class:`StreamFactoryInterface` — a message body, from bytes, from a file, or
  around a file object already open.
- :class:`UriFactoryInterface` — a URI parsed from text.
- :class:`UploadedFileFactoryInterface` — a file that came in with a request.
"""

from __future__ import annotations

from .request_factory_interface import RequestFactoryInterface
from .response_factory_interface import ResponseFactoryInterface
from .server_request_factory_interface import ServerRequestFactoryInterface
from .stream_factory_interface import StreamFactoryInterface
from .uploaded_file_factory_interface import UploadedFileFactoryInterface
from .uri_factory_interface import UriFactoryInterface

__all__ = [
    "RequestFactoryInterface",
    "ResponseFactoryInterface",
    "ServerRequestFactoryInterface",
    "StreamFactoryInterface",
    "UploadedFileFactoryInterface",
    "UriFactoryInterface",
]
