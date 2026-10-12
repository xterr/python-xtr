"""The signature scheme a sender emits and a receiver requires."""

from __future__ import annotations

from enum import StrEnum

from xtr_webhook.exception import InvalidArgumentError

__all__ = ["SignatureFormat"]


class SignatureFormat(StrEnum):
    """Which signature a webhook carries, and therefore what the signature covers.

    The two schemes sign different things, so the choice reaches further than the
    header's spelling: one covers a header and the other covers a timestamp. Both
    ends of a webhook have to have made the same choice, which is why the sender's
    configurators and the receiver's parser each take this.

    The members *are* their strings, so a configuration file, an option mapping or
    an environment variable carries ``"standard"`` and is understood without a
    conversion step — while code that reads them still gets a closed set.

    Attributes:
        LEGACY: This project's historical ``"<algorithm>=<hex>"`` signature, over the
            event name, the id and the body. The event name travels in the
            ``Webhook-Event`` header, which the signature covers. The default, so an
            existing pair of endpoints keeps working.
        STANDARD: The Standard Webhooks ``"v1,<base64>"`` signature, over the id, the
            timestamp and the body (https://www.standardwebhooks.com/). It covers no
            header, so the event name travels in the payload's ``type`` key and the
            ``Webhook-Event`` header is not sent at all. Signing the timestamp is what
            lets a receiver bound replays.
        TRANSITIONAL: Both signatures, space separated, with the event name in both the
            header and the payload. For a migration window: a receiver accepts either,
            and only the Standard Webhooks entry bounds replays.
    """

    LEGACY = "legacy"
    STANDARD = "standard"
    TRANSITIONAL = "transitional"

    @classmethod
    def parse(cls, value: SignatureFormat | str) -> SignatureFormat:
        """Return the member ``value`` stands for.

        The single door for anything arriving from outside — a config option, a
        bundle definition, a caller's keyword — so a typo is refused once, here,
        instead of reaching a signer as an unknown scheme and going out unsigned.

        Args:
            value: A member, or the string one carries.

        Returns:
            The member named by ``value``; a member passes through unchanged.

        Raises:
            InvalidArgumentError: When no member carries that string.
        """
        try:
            return cls(value)
        except ValueError as error:
            raise InvalidArgumentError(
                f'"{value}" is not a signature format; use "legacy", "standard" or "transitional".',
            ) from error
