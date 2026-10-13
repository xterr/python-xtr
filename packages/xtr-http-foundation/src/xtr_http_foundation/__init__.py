"""The request surface an incoming HTTP request is matched and measured against.

A matcher answers one question about a request that arrived — its method, path, host, port,
scheme, a header, a query parameter, an attribute, the address it came from, or whether its
body is JSON — and a chain of them answers the whole of it, so what a piece of code claims is
a value it can be handed rather than a condition written into it.

Beside them are the address helpers those questions are built on: whether an IP falls inside a
network, and whether it is one only this network can reach.
"""

from __future__ import annotations

from .ip_utils import IpUtils

__all__ = ["IpUtils"]
