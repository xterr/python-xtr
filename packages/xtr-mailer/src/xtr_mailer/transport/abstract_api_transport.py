"""The base of every transport that hands a provider's API an email's fields, not its bytes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from typing_extensions import override
from xtr_mime import Message, MessageConverter, MimeError

from xtr_mailer._error_text import type_name
from xtr_mailer.exception import MailerRuntimeError
from xtr_mailer.sent_message import SentMessage

from .abstract_http_transport import AbstractHttpTransport

if TYPE_CHECKING:
    from xtr_http_client_contracts import HttpResponseInterface
    from xtr_mime import Address, Email, RawMessage

    from xtr_mailer.envelope import Envelope

__all__ = ["AbstractApiTransport"]


class AbstractApiTransport(AbstractHttpTransport, ABC):
    """Sends an email as the fields of the API call :meth:`_do_send_api` builds from it.

    The call is built from an :class:`~xtr_mime.Email`: a message is read back into one by
    :class:`~xtr_mime.MessageConverter`, and raw bytes — which have no fields to read — are
    refused; an SMTP transport sends those.

    The email is never rendered: the provider builds the message from the fields it is given,
    so an email the rendering engine would refuse — a ``Subject`` of a single word longer than
    a line may be — is sent all the same. Its ``Message-ID`` is still generated, and the sent
    message renders it the first time anything reads its bytes, raising there what the engine
    refuses.
    """

    @abstractmethod
    async def _do_send_api(
        self, sent_message: SentMessage, email: Email, envelope: Envelope
    ) -> HttpResponseInterface:
        """Call the provider's API with the fields of ``email``, and return its answer.

        Set the message id the provider answered with on ``sent_message``.

        Raises:
            HttpTransportError: The provider refused the email.
            xtr_http_client_contracts.exception.HttpClientError: The client failed; it is
                turned into a transport error.
        """

    @override
    async def _do_send_http(self, message: SentMessage) -> HttpResponseInterface:
        """Read the email the message is, and call the API with it.

        Raises:
            MailerRuntimeError: The message is raw bytes, or a message too complex to be read
                back into an email.
        """
        original = message.get_original_message()
        if not isinstance(original, Message):
            raise MailerRuntimeError(
                f'Unable to send message with the "{type_name(type(self))}" transport: the '
                f'message must be an instance of "{type_name(Message)}" (got '
                f'"{type_name(type(original))}"). An API transport builds its payload from the '
                "message fields; use an SMTP transport to send a raw message."
            )
        try:
            email = MessageConverter.to_email(original)
        except MimeError as error:
            raise MailerRuntimeError(
                f'Unable to send message with the "{type_name(type(self))}" transport: {error}'
            ) from error
        return await self._do_send_api(message, email, message.get_envelope())

    @override
    def _sent_message(self, message: RawMessage, envelope: Envelope) -> SentMessage:
        """Check ``message``, leaving it unrendered: the API is given fields, not bytes."""
        return SentMessage(message, envelope, render_now=False)

    def _get_recipients(self, email: Email, envelope: Envelope) -> list[Address]:
        """Return the envelope's recipients, but the email's copy and hidden recipients.

        What a provider takes as the ``to`` of an API call, the copies going in fields of their
        own, so a copy is never sent twice. A recipient is told from a copy by its address, not
        by the object holding it: reading a message back into an email, or an envelope from the
        email's headers, copies the addresses. Any other recipient of the envelope is kept.
        """
        copies = {copy.get_address() for copy in (*email.get_cc(), *email.get_bcc())}
        return [
            recipient
            for recipient in envelope.get_recipients()
            if recipient.get_address() not in copies
        ]
