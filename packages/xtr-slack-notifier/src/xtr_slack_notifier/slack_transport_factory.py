"""Building the Slack transport from a ``slack://`` DSN."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_notifier.exception import UnsupportedSchemeError
from xtr_notifier.transport import AbstractTransportFactory

from .slack_transport import SlackTransport

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_notifier.transport import Dsn

__all__ = ["SlackTransportFactory"]


@final
class SlackTransportFactory(AbstractTransportFactory):
    """Builds a :class:`SlackTransport` from ``slack://TOKEN@default?channel=CHANNEL``.

    ``default`` stands for ``slack.com``; ``channel`` is the channel posted to
    when a message names none; ``ssl=false`` reaches the host over plain HTTP.
    """

    @override
    def create(self, dsn: Dsn) -> SlackTransport:
        """Build the transport ``dsn`` describes.

        Raises:
            UnsupportedSchemeError: If the scheme is not ``slack``.
            IncompleteDsnError: If the DSN carries no token.
            InvalidArgumentError: If the token is not of a kind Slack issues, or
                ``ssl`` is not a boolean.
        """
        if dsn.scheme != "slack":
            raise UnsupportedSchemeError(dsn.scheme, "slack", self._get_supported_schemes())
        transport = SlackTransport(
            self._get_user(dsn),
            dsn.get_option("channel"),
            self._http_client,
            self._event_dispatcher,
        )
        return (
            transport.set_host(None if dsn.host == "default" else dsn.host)
            .set_port(dsn.port)
            .set_ssl(self._get_ssl(dsn))
        )

    @override
    def _get_supported_schemes(self) -> Sequence[str]:
        """Serve ``slack`` only."""
        return ("slack",)
