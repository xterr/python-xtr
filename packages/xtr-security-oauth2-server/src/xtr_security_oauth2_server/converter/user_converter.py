"""Turning the user a firewall resolved into the one a token names."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_oauth2_server.entity.user import User

from .user_converter_interface import UserConverterInterface

if TYPE_CHECKING:
    from xtr_security_core.user.user_interface import UserInterface

    from xtr_security_oauth2_server.entities.user_entity_interface import UserEntityInterface

__all__ = ["UserConverter"]


@final
class UserConverter(UserConverterInterface):
    """Keeps a user's identifier and drops everything else.

    The roles a firewall reads, the attributes an application hangs off its
    user class, whatever loaded it — none of that crosses into the protocol.
    What comes out answers to one question, which is the only one a token and
    a resource server ever ask.

    Holds nothing, so one instance serves the whole process.
    """

    @override
    def __repr__(self) -> str:
        """Name the type; there is no state to show."""
        return f"{type(self).__name__}()"

    @override
    def to_entity(self, user: UserInterface) -> UserEntityInterface:
        """Return the resource owner ``user`` is, as the protocol names it."""
        entity = User()
        entity.set_identifier(user.get_user_identifier())

        return entity
