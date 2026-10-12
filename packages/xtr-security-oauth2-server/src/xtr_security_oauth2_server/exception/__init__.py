"""The errors the bundle raises beside the library's.

Each derives from the library's :class:`~xtr_security_oauth2_server_core.exception.OAuth2Error`,
so one ``except OAuth2Error`` still catches anything the library or the bundle
raises.

- :class:`ClientAlreadyRegisteredError` — an identifier a client was to be
  registered under that another client already holds.
- :class:`InvalidConfigurationError` — a deployment's configuration the bundle
  cannot turn into a server, named setting by setting.
"""

from __future__ import annotations

from .client_already_registered_error import ClientAlreadyRegisteredError
from .invalid_configuration_error import InvalidConfigurationError

__all__ = [
    "ClientAlreadyRegisteredError",
    "InvalidConfigurationError",
]
