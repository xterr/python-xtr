"""The request the server hands over while consent is being resolved.

An authorization request is read, validated, and then has to wait: who the
resource owner is and whether they approve is decided somewhere else — a
consent page, a listener, an application's own logic — and only then can the
redirect be built. :class:`AuthorizationRequest` is what carries the decided
part across that gap, and
:class:`AuthorizationRequestInterface` is what a deployment implements when it
needs to carry something of its own across it too.
"""

from __future__ import annotations

from .authorization_request import AuthorizationRequest
from .authorization_request_interface import AuthorizationRequestInterface

__all__ = ["AuthorizationRequest", "AuthorizationRequestInterface"]
