"""The answers the authorization server hands back.

A grant decides what a request has earned; a response type decides what the
answer looks like. Keeping them apart is what lets one deployment hand out a
plain token document and another hand out one carrying fields of its own,
without a grant knowing which.

- :class:`ResponseTypeInterface` — what a grant sets what it issued on.
- :class:`AbstractResponseType` — the state every response type is handed.
- :class:`BearerTokenResponse` — the token document a client is handed.
- :class:`RedirectResponse` — the redirect an authorization request ends in.
- :class:`DeviceCodeResponse` — the two codes a device is answered with.
- :class:`IntrospectionResponseTypeInterface` — what a document about a token
  is built through.
- :class:`IntrospectionResponse` — what is said about a token asked about.
"""

from __future__ import annotations

from .abstract_response_type import AbstractResponseType
from .bearer_token_response import BearerTokenResponse
from .device_code_response import DeviceCodeResponse
from .introspection_response import IntrospectionResponse
from .introspection_response_type_interface import IntrospectionResponseTypeInterface
from .redirect_response import RedirectResponse
from .response_type_interface import ResponseTypeInterface

__all__ = [
    "AbstractResponseType",
    "BearerTokenResponse",
    "DeviceCodeResponse",
    "IntrospectionResponse",
    "IntrospectionResponseTypeInterface",
    "RedirectResponse",
    "ResponseTypeInterface",
]
