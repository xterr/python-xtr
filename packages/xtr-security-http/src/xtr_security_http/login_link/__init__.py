"""The login-link suite: a signed link minted for a user, and followed back.

A login may be asked to arrive by a link — an e-mail, a message — and
the pieces here are the one voice on what that link carries: the details
of one minted link, the interface every handler answers, and the handler
that signs its links with the core hasher and checks the ones presented
back, storing nothing.
"""

from __future__ import annotations

from .login_link_details import LoginLinkDetails
from .login_link_handler import LoginLinkHandler
from .login_link_handler_interface import LoginLinkHandlerInterface

__all__ = [
    "LoginLinkDetails",
    "LoginLinkHandler",
    "LoginLinkHandlerInterface",
]
