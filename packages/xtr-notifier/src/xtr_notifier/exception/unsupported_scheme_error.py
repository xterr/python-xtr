"""A DSN whose scheme no installed factory serves."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, distribution
from typing import TYPE_CHECKING

from .logic_error import LogicError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = ["UnsupportedSchemeError"]

#: The provider libraries published alongside this one, by the scheme they serve. A scheme
#: listed here whose library is absent is a missing install, and the error says what to add.
_SCHEME_TO_DISTRIBUTION: Mapping[str, str] = {
    "slack": "xtr-slack-notifier",
    "telegram": "xtr-telegram-notifier",
}


class UnsupportedSchemeError(LogicError):
    """No factory serves a DSN's scheme.

    The common cause is a provider library that is not installed, so a scheme
    a first-party provider library serves is answered with the command that
    installs it. Any other scheme is answered with the schemes that are
    supported, when the caller knows them. The message names the scheme only:
    never the DSN, which carries credentials.

    Attributes:
        scheme: The scheme no factory serves.
        name: What was looking for a factory — ``"chatter"``, ``"texter"`` — or ``None``.
        supported: The schemes that are supported there.
    """

    scheme: str
    name: str | None
    supported: tuple[str, ...]

    def __init__(self, scheme: str, name: str | None = None, supported: Sequence[str] = ()) -> None:
        """Explain why ``scheme`` has no transport.

        Takes the scheme rather than the DSN, so nothing that carries credentials
        ever reaches an error.

        Args:
            scheme: The scheme of the DSN no factory serves.
            name: What was looking for a factory, named in the message with ``supported``.
            supported: The schemes that are supported there.
        """
        self.scheme = scheme
        self.name = name
        self.supported = tuple(supported)
        provider = scheme.partition("+")[0]
        package = _SCHEME_TO_DISTRIBUTION.get(provider)
        if package is not None and not _installed(package):
            super().__init__(
                f'Unable to send notification via "{provider}" as the bridge is not installed. '
                f'Try running "uv add {package}".'
            )
            return
        message = f'The "{scheme}" scheme is not supported'
        if name and self.supported:
            listed = '", "'.join(self.supported)
            message += f'; supported schemes for notifier "{name}" are: "{listed}"'
        super().__init__(f"{message}.")


def _installed(package: str) -> bool:
    """Tell whether the distribution ``package`` is installed."""
    try:
        _ = distribution(package)
    except PackageNotFoundError:
        return False
    return True
