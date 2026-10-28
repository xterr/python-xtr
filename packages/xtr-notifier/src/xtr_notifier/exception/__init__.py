"""The errors the notifier raises, every one a :class:`NotifierError`."""

from __future__ import annotations

from .incomplete_dsn_error import IncompleteDsnError
from .invalid_argument_error import InvalidArgumentError
from .length_error import LengthError
from .logic_error import LogicError
from .missing_required_option_error import MissingRequiredOptionError
from .multiple_exclusive_options_used_error import MultipleExclusiveOptionsUsedError
from .notifier_error import NotifierError
from .notifier_runtime_error import NotifierRuntimeError
from .transport_error import TransportError
from .unsupported_message_type_error import UnsupportedMessageTypeError
from .unsupported_options_error import UnsupportedOptionsError
from .unsupported_scheme_error import UnsupportedSchemeError

__all__ = [
    "IncompleteDsnError",
    "InvalidArgumentError",
    "LengthError",
    "LogicError",
    "MissingRequiredOptionError",
    "MultipleExclusiveOptionsUsedError",
    "NotifierError",
    "NotifierRuntimeError",
    "TransportError",
    "UnsupportedMessageTypeError",
    "UnsupportedOptionsError",
    "UnsupportedSchemeError",
]
