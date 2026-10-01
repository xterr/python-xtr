"""A configured application exercising the provider, extractor and hasher wiring.

An in-memory user provider, a chain over it, an access-token authenticator with
several extractors, password hashers and vote tracing — so a container test
reaches the wiring paths the served fixtures do not.
"""

from __future__ import annotations
