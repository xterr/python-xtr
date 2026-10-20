"""A recipient with an email address, a phone number, or both."""

from __future__ import annotations

from typing import ClassVar

from typing_extensions import override

from xtr_notifier.exception import InvalidArgumentError

from .email_recipient_interface import EmailRecipientInterface
from .sms_recipient_interface import SmsRecipientInterface

__all__ = ["Recipient"]


class Recipient(EmailRecipientInterface, SmsRecipientInterface):
    """Someone reachable by email, by text message, or both.

    An application's own user class can be a recipient by having an ``email``
    or a ``phone``; this one is for a recipient that is nothing else, such as an
    administrator read from configuration. Either value may be changed after
    it is built.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_email", "_phone")

    _email: str
    _phone: str

    def __init__(self, email: str = "", phone: str = "") -> None:
        """Hold the address and the number, at least one of which is needed.

        Args:
            email: The address to write to, or ``""``.
            phone: The phone number, international form with no spaces, or ``""``.

        Raises:
            InvalidArgumentError: If both are empty: the recipient could not be reached.
        """
        if not email and not phone:
            raise InvalidArgumentError(
                f'"{type(self).__name__}" needs an email or a phone but both cannot be empty.'
            )
        self._email = email
        self._phone = phone

    @property
    @override
    def email(self) -> str:
        """The address to write to, or ``""``."""
        return self._email

    @email.setter
    def email(self, email: str) -> None:
        self._email = email

    @property
    @override
    def phone(self) -> str:
        """The phone number, international form with no spaces, or ``""``."""
        return self._phone

    @phone.setter
    def phone(self, phone: str) -> None:
        self._phone = phone
