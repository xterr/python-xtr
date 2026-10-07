"""The bag of badges an authenticator hands to the passport check."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, TypeVar

from xtr_security_core.exception import BadCredentialsError

from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from xtr_security_core.user.user_interface import UserInterface

    from .badge.badge_interface import BadgeInterface

__all__ = ["Passport"]

_BadgeT = TypeVar("_BadgeT", bound="BadgeInterface")


class Passport:
    """What an authenticator produced from a request, before a token exists.

    A passport always carries a
    :class:`~xtr_security_http.authenticator.passport.badge.user_badge.UserBadge`
    naming the user, and any number of other badges — credentials to verify, a
    note to upgrade a password. Listeners resolve the badges during the
    passport check; :meth:`get_user` loads the user through the user badge.
    Attributes are a scratch space listeners and the authenticator share while
    building the token.

    Badges are keyed by class: a passport carries at most one of each kind.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_attributes", "_badges")

    def __init__(
        self,
        user_badge: UserBadge,
        badges: Iterable[BadgeInterface] = (),
        attributes: Mapping[str, object] | None = None,
    ) -> None:
        """Record the user badge and any other badges, keyed by their class."""
        self._badges: dict[type, BadgeInterface] = {}
        _ = self.add_badge(user_badge)
        for badge in badges:
            _ = self.add_badge(badge)
        self._attributes: dict[str, object] = dict(attributes) if attributes is not None else {}

    def add_badge(self, badge: BadgeInterface) -> Passport:
        """Attach ``badge``, replacing any badge of its exact class, and return self.

        Badges are keyed by ``type(badge)`` — the exact runtime class, not a base
        class — so a subclass of a badge does not replace, and is not found by,
        the base class it derives from.
        """
        self._badges[type(badge)] = badge
        return self

    def has_badge(self, badge_class: type[BadgeInterface]) -> bool:
        """Tell whether a badge of ``badge_class`` is attached."""
        return badge_class in self._badges

    def get_badge(self, badge_class: type[_BadgeT]) -> _BadgeT | None:
        """Return the badge of ``badge_class``, or ``None`` when none is attached.

        The lookup is by exact class: a badge is found only under the class it was
        attached as, never under a base class of it.
        """
        badge = self._badges.get(badge_class)
        return badge if isinstance(badge, badge_class) else None

    def get_badges(self) -> Mapping[type, BadgeInterface]:
        """Return every badge attached, keyed by class."""
        return dict(self._badges)

    def get_user_badge(self) -> UserBadge:
        """Return the user badge every passport carries."""
        badge = self._badges[UserBadge]
        assert isinstance(badge, UserBadge)  # noqa: S101 -- construction guarantees it
        return badge

    async def get_user(self) -> UserInterface:
        """Load and return the user through the user badge."""
        return await self.get_user_badge().get_user()

    def get_attribute(self, name: str, default: object = None) -> object:
        """Return the attribute ``name``, or ``default`` when it is not set."""
        return self._attributes.get(name, default)

    def set_attribute(self, name: str, value: object) -> None:
        """Attach ``value`` under ``name`` on the passport."""
        self._attributes[name] = value

    def get_attributes(self) -> Mapping[str, object]:
        """Return every attribute attached to the passport."""
        return dict(self._attributes)

    def check_if_completely_resolved(self) -> None:
        """Raise unless every badge reports itself resolved.

        Raises:
            BadCredentialsError: When any badge is still unresolved once the
                passport check is done — a credential nobody verified, a user
                badge no provider gave a loader.
        """
        for badge in self._badges.values():
            if not badge.is_resolved():
                raise BadCredentialsError(
                    f"The badge {type(badge).__name__} was not resolved by the passport check.",
                )
