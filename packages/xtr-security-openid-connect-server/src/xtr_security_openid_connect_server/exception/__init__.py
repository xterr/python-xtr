"""The errors this package raises, one family under one base.

Every error derives from :class:`OpenIdConnectServerError`, itself an
:class:`~xtr_security_oauth2_server_core.exception.OAuth2Error`, so one
``except OAuth2Error`` still catches anything the authorization server or its
identity layer raises.

- :class:`OpenIdConnectServerError` — the base of them all.
"""

from __future__ import annotations

from .open_id_connect_server_error import OpenIdConnectServerError

__all__ = ["OpenIdConnectServerError"]
