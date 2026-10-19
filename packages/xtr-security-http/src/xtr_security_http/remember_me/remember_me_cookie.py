"""The remember-me cookie a handler staged, before any response existed."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from xtr_http_foundation import cleared_cookie_header_value, cookie_header_value

if TYPE_CHECKING:
    from datetime import datetime

__all__ = ["RememberMeCookie"]


@final
@dataclass(frozen=True, slots=True)
class RememberMeCookie:
    """One remember-me cookie, staged on the request until a response exists.

    A handler sets or clears the cookie while the request is still being
    authenticated — long before anything is sent — so it stages the whole
    cookie here, and the response pass moves it onto the outgoing head. The
    value is the cookie's own: ``None`` means the cookie is being cleared,
    which is not the same as being set to nothing, because the caller that
    staged a clear wants the browser to drop what it holds.

    Attributes:
        name: The cookie's name.
        value: The cookie's value; ``None`` to clear the cookie.
        expires: When the cookie stops being kept; ``None`` for one that
            lives for the session. A cleared cookie carries none — clearing
            dates it behind now on its own.
        path: The path the cookie is available under; the whole site by
            default.
        domain: The domain the cookie is available to; every host that reads
            it when ``None``.
        secure: Whether the cookie travels only over a secure connection.
        httponly: Whether the cookie stays out of the scripts a page runs.
        samesite: Whether the cookie travels on cross-site requests —
            ``"lax"``, ``"strict"`` or ``"none"`` — or ``None`` to write no
            attribute.
    """

    name: str
    value: str | None
    expires: datetime | None = None
    path: str | None = "/"
    domain: str | None = None
    secure: bool = False
    httponly: bool = True
    samesite: str | None = None

    def header_value(self) -> str:
        """Return the value a ``Set-Cookie`` header carries for this cookie.

        Setting and clearing are the one operation read two ways: a value is
        written with its expiry, and the lack of one writes the form a
        browser answers by dropping the cookie — dated behind now, on the
        same path and domain it was set under, because a browser tells its
        cookies apart by all three.
        """
        if self.value is None:
            return cleared_cookie_header_value(
                self.name,
                path=self.path,
                domain=self.domain,
                secure=self.secure,
                httponly=self.httponly,
                samesite=self.samesite,
            )
        return cookie_header_value(
            self.name,
            self.value,
            expires=self.expires,
            path=self.path,
            domain=self.domain,
            secure=self.secure,
            httponly=self.httponly,
            samesite=self.samesite,
        )
