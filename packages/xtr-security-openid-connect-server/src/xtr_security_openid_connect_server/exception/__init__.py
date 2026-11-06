"""The errors this package raises, one family under one base.

Every error derives from :class:`OpenIdConnectServerError`, itself an
:class:`~xtr_security_oauth2_server_core.exception.OAuth2Error`, so one
``except OAuth2Error`` still catches anything the authorization server or its
identity layer raises.

- :class:`OpenIdConnectServerError` — the base of them all.
- :class:`InvalidArgumentError` — one of this package's own objects used
  wrongly, which is a caller's mistake and nobody's answer.
- :class:`InvalidConfigurationError` — a deployment's configuration the
  identity layer cannot be built out of, named setting by setting.
- :class:`UnsupportedAlgorithmError` — a signature algorithm that names no
  digest, so an ID token signed with it can carry no token hash.
"""

from __future__ import annotations

from .invalid_argument_error import InvalidArgumentError
from .invalid_configuration_error import InvalidConfigurationError
from .open_id_connect_server_error import OpenIdConnectServerError
from .unsupported_algorithm_error import UnsupportedAlgorithmError

__all__ = [
    "InvalidArgumentError",
    "InvalidConfigurationError",
    "OpenIdConnectServerError",
    "UnsupportedAlgorithmError",
]
