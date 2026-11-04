"""Signs every email with DKIM."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Final, final

from xtr_mime import Message

if TYPE_CHECKING:
    from xtr_mime.crypto import DkimSigner

    from xtr_mailer.event import MessageEvent

__all__ = ["DkimSignedMessageListener"]


@final
class DkimSignedMessageListener:
    """Replaces every email with the same email signed by the signer.

    Listen to :class:`~xtr_mailer.event.MessageEvent` with :meth:`on_message` at
    :attr:`PRIORITY`, after the listeners changing the headers, so the signature covers the
    headers sent. The signed email keeps its Bcc, which is never sent, so the envelope read
    from it still reaches the hidden recipients; its body is the one signed, so it is sent as
    the same bytes. Raw bytes are sent unsigned. Needs the ``dkim`` extra.
    """

    #: Run after the listeners changing the email, before the envelope is set.
    PRIORITY: Final = -228

    __slots__: ClassVar[tuple[str, ...]] = ("_signer",)

    def __init__(self, signer: DkimSigner) -> None:
        """Sign with ``signer``."""
        self._signer: DkimSigner = signer

    def on_message(self, event: MessageEvent) -> None:
        """Replace ``event``'s email with the signed one.

        Raises:
            MimeRuntimeError: As signing does — the email has no From to sign.
            RfcComplianceError: As rendering the email does.
        """
        message = event.get_message()
        if isinstance(message, Message):
            event.set_message(self._signer.sign(message))
