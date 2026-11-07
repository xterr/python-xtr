"""The flow a sign-in runs through.

A sign-in is an authorization code flow that remembers more of the request it
started with: :class:`OpenIdAuthCodeGrant` is the authorization server's own
code flow, carrying the ``nonce`` and the sign-in time through the code to the
token answer that states them.
"""

from __future__ import annotations

from .open_id_auth_code_grant import OpenIdAuthCodeGrant

__all__ = ["OpenIdAuthCodeGrant"]
