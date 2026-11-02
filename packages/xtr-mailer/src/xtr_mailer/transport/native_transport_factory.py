"""Builds the transport of the host's own sendmail from ``native://`` DSNs."""

from __future__ import annotations

import os
import shlex
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override

from xtr_mailer.exception import TransportError, UnsupportedSchemeError

from .abstract_transport_factory import AbstractTransportFactory
from .sendmail_transport import SendmailTransport

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .dsn import Dsn

__all__ = ["FALLBACK_PATH", "NativeTransportFactory"]

FALLBACK_PATH: Final = "/usr/sbin/sendmail"
"""Where the host's sendmail conventionally is, looked at when none is on the ``PATH``."""


@final
class NativeTransportFactory(AbstractTransportFactory):
    """Builds a :class:`SendmailTransport` for ``native://``: the host's sendmail, as configured.

    The program is the ``sendmail`` found on the ``PATH``, else :data:`FALLBACK_PATH` when it
    can be run, and runs as ``<path> -t -i``: the host's mail system, Postfix or another,
    delivers with its own configuration. The program is looked for when the transport is
    built.
    """

    @override
    def create(self, dsn: Dsn) -> SendmailTransport:
        """Build the transport of the host's sendmail.

        Raises:
            UnsupportedSchemeError: ``dsn``'s scheme is not ``native``.
            TransportError: No sendmail program was found.
        """
        if not self.supports(dsn):
            raise UnsupportedSchemeError(dsn.scheme, "native", self._get_supported_schemes())
        path = shutil.which("sendmail")
        if path is None and Path(FALLBACK_PATH).is_file() and os.access(FALLBACK_PATH, os.X_OK):
            path = FALLBACK_PATH
        if path is None:
            raise TransportError(
                'No sendmail binary was found for the "native" transport; use a '
                '"sendmail://default" or "smtp://..." DSN.'
            )
        return SendmailTransport(
            shlex.join([path, "-t", "-i"]),
            event_dispatcher=self._event_dispatcher,
            logger=self._logger,
        )

    @override
    def _get_supported_schemes(self) -> Sequence[str]:
        """Return ``native``, the one scheme served."""
        return ("native",)
