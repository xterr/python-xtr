"""The endpoints that are about a token a client already holds.

A client that is done with a token asks for it to be withdrawn, and a resource
server that cannot read a token asks whether it is live. The two requests are
the same — the same body, the same client authentication, the same reading of
the token — so one handler answers each and everything they share sits
underneath them.

- :class:`TokenHandlerInterface` — what the token server drives either
  endpoint through.
- :class:`AbstractTokenHandler` — reading the token both are handed.
- :class:`TokenRevocationHandler` — RFC 7009, the withdrawal.
- :class:`TokenIntrospectionHandler` — RFC 7662, the question.
- :class:`ValidatedToken` — what a reading accepted, and as which kind.
"""

from __future__ import annotations

from .abstract_token_handler import AbstractTokenHandler
from .token_handler_interface import TokenHandlerInterface
from .token_introspection_handler import TokenIntrospectionHandler
from .token_revocation_handler import TokenRevocationHandler
from .validated_token import ValidatedToken

__all__ = [
    "AbstractTokenHandler",
    "TokenHandlerInterface",
    "TokenIntrospectionHandler",
    "TokenRevocationHandler",
    "ValidatedToken",
]
