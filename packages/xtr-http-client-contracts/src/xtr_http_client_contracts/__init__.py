"""The async HTTP client contract: what code that calls out depends on, and nothing more.

A library that sends an HTTP request should not decide what sends it. It takes the client
interface, asks for a method and a URL, and gets back a response whose status line and headers
have arrived — its body read when, and only when, the caller wants it.

What is here is only what appears in that contract: the client, the response it answers with,
the chunks a streamed body arrives in, the options a request takes, the errors any of them
raises, and a conformance suite an implementation can run against itself.
"""

from __future__ import annotations

__all__: list[str] = []
