"""Signs every email with S/MIME."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Final, final

from xtr_mime import Message

if TYPE_CHECKING:
    from xtr_mime.crypto import SMimeSigner

    from xtr_mailer.event import MessageEvent

__all__ = ["SmimeSignedMessageListener"]


@final
class SmimeSignedMessageListener:
    """Replaces every email with the same email, its body signed by the signer.

    Listen to :class:`~xtr_mailer.event.MessageEvent` with :meth:`on_message` at
    :attr:`PRIORITY`: after the listeners changing the email, before the S/MIME encrypting
    listener — which encrypts the signed email — and before the DKIM listener, whose signature
    covers the S/MIME one. The signed email keeps its headers, Bcc among them, which is never
    sent, so the envelope read from it still reaches the hidden recipients; its body is sent as
    the very bytes signed. Raw bytes are sent unsigned.

    The signer needs the ``smime`` extra: without it, building one raises
    :class:`xtr_mime.LogicError`.
    """

    #: Run after the listeners changing the email, before it is encrypted or signed with DKIM.
    PRIORITY: Final = -128

    __slots__: ClassVar[tuple[str, ...]] = ("_signer",)

    def __init__(self, signer: SMimeSigner) -> None:
        """Sign with ``signer``."""
        self._signer: SMimeSigner = signer

    def on_message(self, event: MessageEvent) -> None:
        """Replace ``event``'s email with the signed one.

        Raises:
            LogicError: As signing does — the email has neither a From nor a Sender.
            RfcComplianceError: As rendering the body does.
        """
        message = event.get_message()
        if isinstance(message, Message):
            event.set_message(self._signer.sign(message))
