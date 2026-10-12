"""Reading a response message back as the response the framework sends."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_kernel.bridge import Response

from xtr_security_oauth2_server.exception.invalid_configuration_error import (
    InvalidConfigurationError,
)

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface

__all__ = ["served"]

_NOT_THE_KERNELS_RESPONSE = (
    "An endpoint of this package was handed a response of type {given!r}, which is an HTTP "
    "message but not a response the framework can send. In an application the two are the "
    "same object: the HTTP kernel registers its own response under both names. Something has "
    "replaced that registration — a bundle aliasing ResponseInterface to a response of its "
    "own — and this package's endpoints cannot answer with it."
)


def served(message: ResponseInterface) -> Response:
    """Return ``message`` as the response an endpoint hands back.

    The library below these controllers answers in terms of the message
    contract: it is handed a response and gives one back, so that it runs in
    front of any framework. A controller, though, is serving a request, and
    what it returns has to be something the framework can send.

    In an application the two are the same object. The kernel registers its own
    response under both names, so the response a controller is handed *is* the
    framework's, and every ``with_*`` on it re-wraps into the same class — so
    whatever the library hands back, having built it from that response, is one
    too. This checks that invariant in the one place it is relied on, rather
    than once per endpoint, and says what has been replaced when it does not
    hold.

    Raises:
        InvalidConfigurationError: When the message is not the kernel's own
            response, which means something has taken over the registration
            the endpoints answer through.
    """
    if not isinstance(message, Response):
        raise InvalidConfigurationError(
            _NOT_THE_KERNELS_RESPONSE.format(given=type(message).__qualname__),
        )

    return message
