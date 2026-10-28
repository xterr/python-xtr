"""A login-link authenticator, described as inert data.

A link mailed to a user is signed — over the user's covered properties,
until a lifetime from when it was minted — and the request that follows it is
the login it carries. The secret the link is signed with is the
application's to supply: the bundle builds and boots without it, and the
handler that needs it fails naming it the first time it is asked for.
"""

from __future__ import annotations

from collections.abc import Sequence  # noqa: TC003 -- field type read at runtime
from dataclasses import dataclass

from xtr_security.exception import InvalidConfigurationError

__all__ = ["LoginLinkConfig"]


@dataclass(frozen=True, slots=True)
class LoginLinkConfig:
    """A login-link authenticator: the signed link a request follows to log in.

    Attributes:
        check_path: The literal path a followed link arrives at — required,
            and refused when empty.
        path: The literal path every minted link leads to — required, and
            refused when empty.
        secret: The secret the link's hash is signed with — the
            application's to supply, never generated. Checked where it is
            used: the bundle builds and boots without it, and the handler
            fails naming it the first time it is asked for.
        lifetime: How many seconds a minted link counts until.
        check_post_only: Whether only a POST to the check path is a followed
            link.
        signature_properties: The user properties whose digest the link's
            hash carries, retiring the link when any of them changes.
        success_handler: The application's own success-handler service type,
            or ``None`` for the default redirect by the target ladder.
        failure_handler: The application's own failure-handler service type,
            or ``None`` for the default answer of a failed login.

    Raises:
        InvalidConfigurationError: When the check path or the link path is
            empty.
    """

    check_path: str
    path: str
    secret: str | None = None
    lifetime: int = 600
    check_post_only: bool = False
    signature_properties: Sequence[str] = ("password",)
    success_handler: type | None = None
    failure_handler: type | None = None

    def __post_init__(self) -> None:
        """Refuse a check path or a link path that names nothing."""
        if not self.check_path:
            raise InvalidConfigurationError(
                "A login link needs the literal check path a followed link arrives at.",
            )
        if not self.path:
            raise InvalidConfigurationError(
                "A login link needs the literal path every minted link leads to.",
            )
