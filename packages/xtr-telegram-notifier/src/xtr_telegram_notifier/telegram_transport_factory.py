"""Building the Telegram transport from a ``telegram://`` DSN."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_notifier.exception import IncompleteDsnError, UnsupportedSchemeError
from xtr_notifier.transport import AbstractTransportFactory

from .telegram_transport import TelegramTransport

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_notifier.transport import Dsn

__all__ = ["TelegramTransportFactory"]


@final
class TelegramTransportFactory(AbstractTransportFactory):
    """Builds a :class:`TelegramTransport` from ``telegram://BOT_ID:TOKEN@default?channel=CHAT_ID``.

    The bot token is the DSN's user and password joined by ``:`` — the token
    as the bot API hands it out. ``default`` stands for ``api.telegram.org``;
    ``channel`` is the chat sent to when a message names none; ``ssl=false``
    (or the older ``sslmode=disable``) reaches the host over plain HTTP.
    """

    @override
    def create(self, dsn: Dsn) -> TelegramTransport:
        """Build the transport ``dsn`` describes.

        Raises:
            UnsupportedSchemeError: If the scheme is not ``telegram``.
            IncompleteDsnError: If the DSN carries no token, or half of one.
            InvalidArgumentError: If ``ssl`` is not a boolean.
        """
        if dsn.scheme != "telegram":
            raise UnsupportedSchemeError(dsn.scheme, "telegram", self._get_supported_schemes())
        ssl = self._get_ssl(dsn)
        transport = TelegramTransport(
            _token(dsn), dsn.get_option("channel"), self._http_client, self._event_dispatcher
        )
        return (
            transport.set_ssl(dsn.get_option("sslmode") != "disable" if ssl is None else ssl)
            .set_host(None if dsn.host == "default" else dsn.host)
            .set_port(dsn.port)
        )

    @override
    def _get_supported_schemes(self) -> Sequence[str]:
        """Serve ``telegram`` only."""
        return ("telegram",)


def _token(dsn: Dsn) -> str:
    """Return the bot token the DSN's user and password make up.

    Raises:
        IncompleteDsnError: Naming the DSN by its host only, never the token.
    """
    shown = f"telegram://{dsn.host}"
    if dsn.user is None and dsn.password is None:
        raise IncompleteDsnError("Missing token.", shown)
    if dsn.password is None:
        raise IncompleteDsnError("Malformed token.", shown)
    return f"{dsn.user}:{dsn.password}"
