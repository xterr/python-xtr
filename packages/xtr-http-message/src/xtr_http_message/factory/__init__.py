"""The factory that builds every kind of message.

One class implements all six factory interfaces, so a library that is handed
it can build a request, a server request, a response, a stream, a URI or an
uploaded file without ever naming the class that is one.

```python
from xtr_http_message.factory import HttpFactory

factory = HttpFactory()
request = factory.create_request("GET", "https://example.com/orders")
assert request.get_header_line("host") == "example.com"
```
"""

from __future__ import annotations

from .http_factory import HttpFactory

__all__ = ["HttpFactory"]
