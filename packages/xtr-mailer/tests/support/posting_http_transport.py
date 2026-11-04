"""An HTTP transport posting each email's bytes to a test provider, reading back its id."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

from typing_extensions import override

from xtr_mailer import HttpTransportError
from xtr_mailer.transport import AbstractHttpTransport

if TYPE_CHECKING:
    from xtr_http_client_contracts import HttpResponseInterface

    from xtr_mailer import SentMessage

__all__ = ["PostingHttpTransport"]


class PostingHttpTransport(AbstractHttpTransport):
    """Posts the rendered email to ``/send`` with a credential, and keeps the ``id`` answered.

    With :attr:`refuse_itself` it raises its own :class:`HttpTransportError` on a status other
    than 200, as a provider's transport does; otherwise reading the answer raises the client's.
    """

    refuse_itself: bool = False

    @override
    async def _do_send_http(self, message: SentMessage) -> HttpResponseInterface:
        host = self._host or "api.example.com"
        endpoint = f"{host}:{self._port}" if self._port else host
        response = await self._http_client.request(
            "POST",
            f"https://{endpoint}/send",
            body=b"".join(message.to_iterable()),
            auth_basic=("api", "key-secret"),
        )
        async with response:
            if self.refuse_itself and response.get_status_code() != HTTPStatus.OK:
                raise HttpTransportError("Refused.", response, response.get_status_code())
            message.set_message_id(str((await response.to_array())["id"]))
        return response

    @override
    def __str__(self) -> str:
        return "posting://api.example.com"
