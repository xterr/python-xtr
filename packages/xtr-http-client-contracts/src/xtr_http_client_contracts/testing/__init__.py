"""What an implementation of the client contract tests itself with.

Install it with the ``testing`` extra. Nothing here is imported by the contract itself, so an
application that only depends on the interfaces never pays for it.
"""

from __future__ import annotations

from .http_client_test_case import HttpClientTestCase
from .test_http_server import TestHttpServer

__all__ = ["HttpClientTestCase", "TestHttpServer"]
