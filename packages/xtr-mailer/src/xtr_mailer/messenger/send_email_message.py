"""An email queued on a message bus, to be sent by a worker."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, final

from typing_extensions import override
from xtr_mime import MimeError

from xtr_mailer.exception import MailerError

from ._wire import read, write

if TYPE_CHECKING:
    from pydantic import GetCoreSchemaHandler
    from pydantic_core import CoreSchema
    from xtr_mime import RawMessage

    from xtr_mailer.envelope import Envelope

    from ._wire import JsonObject

__all__ = ["SendEmailMessage"]


@final
class SendEmailMessage:  # noqa: PLW1641 -- equal by what it travels as, so not hashable.
    """An email and the envelope it is sent with, as the mailer queued them.

    A serializer writes it as plain data and reads it back in the worker as the same classes:
    a raw message as its bytes; a message or an email — an email of a provider's template, a
    draft — as its headers, each of its own class, and its body, or the text, HTML and
    attachments it is put together from, so the listeners of the worker change it as they
    would have here. A file attached is read when the email is queued and travels as its
    content; a body frozen at signing travels as its bytes, and a signed or encrypted email
    sends exactly what was signed. The envelope travels as the sender and recipients it gives.
    Only the mailer's own classes are carried: one of another class is refused when written.

    Two queued emails are equal when they travel as the same data. That data is taken once,
    the first time it is written or compared, so a stream is read once and the email changed
    after is not what travels.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_envelope", "_message", "_written")

    def __init__(self, message: RawMessage, envelope: Envelope | None = None) -> None:
        """Queue ``message``, sent with ``envelope``.

        Args:
            message: The email as the caller gave it, before any listener changed it.
            envelope: The envelope the caller gave; ``None`` sends with the one the email's
                headers give when it is sent.
        """
        self._message: RawMessage = message
        self._envelope: Envelope | None = envelope
        self._written: JsonObject | None = None

    @property
    def message(self) -> RawMessage:
        """The email to send."""
        return self._message

    @property
    def envelope(self) -> Envelope | None:
        """The envelope to send it with; ``None`` for the one its headers give."""
        return self._envelope

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SendEmailMessage):
            return NotImplemented
        return self.written() == other.written()

    @override
    def __repr__(self) -> str:
        """Name the classes only: the email's addresses and content are nobody's log line."""
        envelope = "None" if self._envelope is None else type(self._envelope).__name__
        return f"SendEmailMessage({type(self._message).__name__}, envelope={envelope})"

    def written(self) -> JsonObject:
        """Return the plain data the email and its envelope travel as.

        Raises:
            InvalidArgumentError: The email, or a part or header in it, is of a class the queue
                does not carry, or its parts are nested deeper than 32.
            xtr_mime.MimeError: The email cannot be read: a file attached is gone, a generator
                is left half read.
            MailerError: The envelope cannot be read from the email's headers.
        """
        if self._written is None:
            self._written = write(self._message, self._envelope)
        return self._written

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source: object, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        """Read and write the queued email as the plain data :meth:`written` gives."""
        del source, handler
        # Called only by pydantic, so only with pydantic installed.
        from pydantic_core import core_schema  # noqa: PLC0415 -- see above.

        return core_schema.no_info_plain_validator_function(
            _read,
            serialization=core_schema.plain_serializer_function_ser_schema(_write),
        )


def _read(data: object) -> SendEmailMessage:
    if isinstance(data, SendEmailMessage):
        return data
    return SendEmailMessage(*read(data))


def _write(message: SendEmailMessage) -> JsonObject:
    """Give the data ``message`` travels as; a refusal in the serializer's words when it has one.

    The serializer only believes a refusal of its own: any other error it reports as a value
    with no plain form, and the reason would be lost.
    """
    try:
        return message.written()
    except (MimeError, MailerError) as error:
        refusal = _serializer_refusal(str(error))
        if refusal is None:
            raise
        raise refusal from error


def _serializer_refusal(reason: str) -> Exception | None:
    try:
        # Only a serializer writes a queued email; it is not needed for anything else.
        from xtr_serializer import NotNormalizableValueError  # noqa: PLC0415 -- see above.
    except ImportError:
        return None
    return NotNormalizableValueError(
        reason, current_type="SendEmailMessage", error_type="value_error"
    )
