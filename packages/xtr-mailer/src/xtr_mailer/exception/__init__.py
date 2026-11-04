"""The errors the mailer raises, every one a :class:`MailerError`."""

from __future__ import annotations

from .http_transport_error import HttpTransportError
from .incomplete_dsn_error import IncompleteDsnError
from .invalid_argument_error import InvalidArgumentError
from .logic_error import LogicError
from .mailer_error import MailerError
from .mailer_runtime_error import MailerRuntimeError
from .transport_error import TransportError
from .unexpected_response_error import UnexpectedResponseError
from .unsupported_scheme_error import UnsupportedSchemeError

__all__ = [
    "HttpTransportError",
    "IncompleteDsnError",
    "InvalidArgumentError",
    "LogicError",
    "MailerError",
    "MailerRuntimeError",
    "TransportError",
    "UnexpectedResponseError",
    "UnsupportedSchemeError",
]
