"""The bag of badges an authenticator hands to the passport check."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, TypeVar, cast

from xtr_security_core.exception import AuthenticationServiceError

from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from xtr_security_core.user.user_interface import UserInterface

    from .badge.badge_interface import BadgeInterface
    from .credentials.credentials_interface import CredentialsInterface

__all__ = ["Passport"]

_BadgeT = TypeVar("_BadgeT", bound="BadgeInterface")


class Passport:
    """What an authenticator produced from a request, before a token exists.

    A passport always carries a
    :class:`~xtr_security_http.authenticator.passport.badge.user_badge.UserBadge`
    naming the user and a credential to verify for them, plus any number of
    other badges — a note to upgrade a password, a token to check. Listeners
    resolve the badges during the passport check; :meth:`get_user` loads the
    user through the user badge. Attributes are a scratch space listeners and
    the authenticator share while building the token.

    Badges are keyed by class: a passport carries at most one of each kind.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_attributes", "_badges", "_user")

    def __init__(
        self,
        user_badge: UserBadge,
        credentials: CredentialsInterface,
        badges: Iterable[BadgeInterface] = (),
        attributes: Mapping[str, object] | None = None,
    ) -> None:
        """Record the user badge, the credentials and any other badges."""
        self._badges: dict[type, BadgeInterface] = {}
        self._user: UserInterface | None = None
        _ = self.add_badge(user_badge)
        _ = self.add_badge(credentials)
        for badge in badges:
            _ = self.add_badge(badge)
        self._attributes: dict[str, object] = dict(attributes) if attributes is not None else {}

    def add_badge(
        self,
        badge: BadgeInterface,
        badge_class: type[BadgeInterface] | None = None,
    ) -> Passport:
        """Attach ``badge`` under ``badge_class``, and return self.

        Badges are keyed by class: a passport carries at most one of each kind,
        and a later badge replaces the earlier one under the same key. The key
        defaults to ``type(badge)`` — the exact runtime class — and may be
        given explicitly, so a custom badge can stand in for a built-in one.
        """
        self._badges[badge_class if badge_class is not None else type(badge)] = badge
        return self

    def has_badge(self, badge_class: type[BadgeInterface]) -> bool:
        """Tell whether a badge of ``badge_class`` is attached."""
        return badge_class in self._badges

    def get_badge(self, badge_class: type[_BadgeT]) -> _BadgeT | None:
        """Return the badge attached under ``badge_class``, or ``None`` when none is.

        The lookup is by key: a badge attached under an explicit class — a
        custom badge standing in for a built-in — is found under that class.
        """
        return cast("_BadgeT | None", self._badges.get(badge_class))

    def get_badges(self) -> Mapping[type, BadgeInterface]:
        """Return every badge attached, keyed by class."""
        return dict(self._badges)

    def get_user_badge(self) -> UserBadge:
        """Return the user badge every passport carries.

        Raises:
            AuthenticationServiceError: When no user badge is attached, which
                only a hand-built passport could lack.
        """
        badge = self._badges.get(UserBadge)
        if not isinstance(badge, UserBadge):
            raise AuthenticationServiceError(
                "The passport carries no user badge, so there is no user to load.",
            )
        return badge

    async def get_user(self) -> UserInterface:
        """Load the user through the user badge once, and return it cached.

        Raises:
            AuthenticationServiceError: When no user badge is attached.
        """
        if self._user is None:
            self._user = await self.get_user_badge().get_user()
        return self._user

    def get_attribute(self, name: str, default: object = None) -> object:
        """Return the attribute ``name``, or ``default`` when it is not set."""
        return self._attributes.get(name, default)

    def set_attribute(self, name: str, value: object) -> None:
        """Attach ``value`` under ``name`` on the passport."""
        self._attributes[name] = value

    def get_attributes(self) -> Mapping[str, object]:
        """Return every attribute attached to the passport."""
        return dict(self._attributes)
