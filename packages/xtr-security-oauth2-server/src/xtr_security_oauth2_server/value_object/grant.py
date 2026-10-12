"""One grant type a client is registered for."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from typing_extensions import override
from xtr_security_oauth2_server_core.exception.invalid_argument_error import InvalidArgumentError

__all__ = ["Grant"]


@final
@dataclass(frozen=True, slots=True)
class Grant:
    """A grant type, named by the identifier the protocol gives it.

    A client's registration is a list of these, and a request is refused when
    the grant it names is not among them. Two grants of one name are the same
    grant, so that check is a plain containment test rather than a comparison
    of strings pulled back out.

    There is no such thing as a nameless grant, so an empty name is refused
    where it is made rather than silently matching nothing later.
    """

    grant: str

    def __post_init__(self) -> None:
        """Refuse a grant with no name.

        Raises:
            InvalidArgumentError: When ``grant`` is empty.
        """
        if self.grant == "":
            raise InvalidArgumentError(
                "A grant has to be named; an empty grant type matches no request and "
                "would be stored as a registration that can never be used.",
            )

    @override
    def __str__(self) -> str:
        """Return the grant type, so a grant reads and serialises as its name."""
        return self.grant
