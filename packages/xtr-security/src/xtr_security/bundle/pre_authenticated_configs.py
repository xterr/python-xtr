"""The pre-authenticated authenticators' tagged configuration union.

Two kinds of request arrive already authenticated — one where the server in
front of the application named the account, one where the client's own
certificate did — and the firewall picks between them by the ``type`` field
each configuration carries. The two share this module: they are the variants
of one tagged union, the configuration an access rule picks between.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

__all__ = ["RemoteUserConfig", "X509Config"]


@dataclass(frozen=True, slots=True)
class RemoteUserConfig:
    """A pre-authenticated authenticator reading the account the server named.

    A server that authenticated the request before the application saw it
    writes the account it identified as into the environment the request
    arrives with, under one key; this authenticator reads that key and takes
    its value as the username, proven by the server in front.

    Attributes:
        user_key: The environment key the server in front wrote the
            authenticated account under.
    """

    type: Literal["remote_user"] = "remote_user"
    user_key: str = "REMOTE_USER"


@dataclass(frozen=True, slots=True)
class X509Config:
    """A pre-authenticated authenticator reading the client's certificate.

    The server the request arrived through verified the client's certificate
    and wrote its claims into the environment; this authenticator reads the
    email address out of it, or the whole distinguished name when there is no
    email, taking the identifier it finds as the username, proven by the
    certificate's own signature.

    Attributes:
        user_key: The environment key the server wrote the verified
            certificate's email address under.
        credentials_key: The environment key the server wrote the whole
            distinguished name under.
        credential_user_identifier: The distinguished-name identifier the
            username is read out of when the email key is absent;
            ``emailAddress`` also answers its dotted OID spelling.
    """

    type: Literal["x509"] = "x509"
    user_key: str = "SSL_CLIENT_S_DN_Email"
    credentials_key: str = "SSL_CLIENT_S_DN"
    credential_user_identifier: str = "emailAddress"
