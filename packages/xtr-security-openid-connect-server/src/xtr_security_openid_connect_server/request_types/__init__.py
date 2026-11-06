"""The authorization request a sign-in carries while consent is being resolved.

An authorization request is read, validated, and then waits for the resource
owner's decision. A sign-in has more to carry across that wait than the
shipped request holds — the ``nonce`` its ID token repeats back, the
``prompt`` and ``max_age`` it was asked with, and when the end-user last
signed in — so :class:`OpenIdAuthorizationRequest` extends that request with
them, and the grant fills in everything else as it always did.
"""

from __future__ import annotations

from .open_id_authorization_request import OpenIdAuthorizationRequest

__all__ = ["OpenIdAuthorizationRequest"]
