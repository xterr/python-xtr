"""The endpoints an application serves this authorization server through.

Each is a service the bundle builds from the deployment's configuration, and
each takes the request being served and the response to answer with as HTTP
messages — so what reads a request and fills in a response knows nothing of the
web framework underneath. The route loaders in
:mod:`xtr_security_oauth2_server.routing` contribute the endpoints calling them.
"""

from __future__ import annotations

from .authorization_controller import AuthorizationController
from .device_code_controller import DeviceCodeController
from .introspection_controller import IntrospectionController
from .jwks_controller import JwksController
from .metadata_controller import MetadataController
from .revocation_controller import RevocationController
from .token_controller import TokenController

__all__ = [
    "AuthorizationController",
    "DeviceCodeController",
    "IntrospectionController",
    "JwksController",
    "MetadataController",
    "RevocationController",
    "TokenController",
]
