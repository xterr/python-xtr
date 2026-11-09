"""The listeners the provider adds to the application's dispatcher.

:func:`stamp_auth_time` records, on a sign-in's authorization request, when the
end-user last signed in, ahead of the application's consent listener; that
listener runs below :data:`AUTH_TIME_LISTENER_PRIORITY`.
"""

from __future__ import annotations

from .auth_time_listener import AUTH_TIME_LISTENER_PRIORITY, stamp_auth_time

__all__ = ["AUTH_TIME_LISTENER_PRIORITY", "stamp_auth_time"]
