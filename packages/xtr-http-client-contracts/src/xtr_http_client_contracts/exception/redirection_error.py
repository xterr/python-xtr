"""The answer points somewhere else, and nobody is following it any further."""

from __future__ import annotations

from .http_error import HttpError

__all__ = ["RedirectionError"]


class RedirectionError(HttpError):
    """A 3xx status that was not followed.

    Raised once ``max_redirects`` has been reached, or straight away when
    following was turned off with ``max_redirects`` of zero or less — a
    redirect that *is* followed never reaches the caller, since what comes
    back is the response from the last hop.

    Where the answer points is in the ``redirect_url`` entry of
    :meth:`HttpResponseInterface.get_info
    <xtr_http_client_contracts.http_response_interface.HttpResponseInterface.get_info>`.
    """
