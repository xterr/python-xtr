"""The default limits a login's failed attempts count under.

A failed login is counted twice — under the account it named and under
the address it came from — because the two together close the two ways
an anonymous caller has to keep trying: naming many accounts from one
address, and naming one account from many addresses. The keys are
derived here, from a secret the application supplies, so the counts a
store keeps name no account and no address in the clear.
"""

from __future__ import annotations

import base64
import hmac
from collections.abc import MutableMapping, Sequence
from hashlib import sha256
from typing import TYPE_CHECKING, Final, cast, final

from typing_extensions import override
from xtr_http_foundation import AbstractRequestRateLimiter, RateLimiterInterface
from xtr_security_core.exception import InvalidArgumentError

from xtr_security_http._security_state import security_state_of
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_rate_limiter import LimiterInterface, RateLimiterFactoryInterface

__all__ = ["DefaultLoginRateLimiter"]

_CLIENT: Final = "client"
"""Where the server reports who it is talking to: the address first, then the port."""

_KEY_ALPHABET: Final = str.maketrans("/+", "._")
"""The base64 alphabet's wire-unsafe pair, replaced with characters a key can carry."""


@final
class DefaultLoginRateLimiter(AbstractRequestRateLimiter):
    """Counts a login under the account it named and the address it came from.

    Two limits, one strict each way: the local one counts the attempts on one
    account from one address, and the global one counts everything one address
    tries, across accounts — a breadth-first sweep of usernames is bounded
    even when no single account sees two attempts. Both keys are HMAC
    digests of what they name, prefixed with a secret the application
    supplies, so a store shared across servers keeps no readable account or
    address.

    A successful login forgets the local count only: the global one bounds
    how many accounts one client may try, so it must survive the successful
    login of any one of them.
    """

    def __init__(
        self,
        global_factory: RateLimiterFactoryInterface,
        local_factory: RateLimiterFactoryInterface,
        secret: str,
    ) -> None:
        """Record the two factories and the secret their keys are derived with.

        Args:
            global_factory: The factory handing out the limiters one address
                counts under.
            local_factory: The factory handing out the limiters one account
                from one address counts under.
            secret: The secret the keys are derived with.

        Raises:
            InvalidArgumentError: When ``secret`` is empty — a key derived
                with no secret names what it counts in the clear.
        """
        if not secret:
            raise InvalidArgumentError("A non-empty secret is required.")
        self._global_factory = global_factory
        self._local_factory = local_factory
        self._secret = secret

    @override
    def get_limiters(self, request: ServerRequestInterface) -> Sequence[RateLimiterInterface]:
        """Return the limiters a login attempt counts under.

        The global limiter counts the address, the local one the account
        from that address — the username read off the request's security
        state, where the throttling listener parks it, lower-cased so the
        same account is one account whatever capitalisation it arrived with.
        """
        return [
            self._global_factory.create(self._hash(_client_address(request))),
            self._local_limiter(request),
        ]

    @override
    async def reset(self, request: ServerRequestInterface) -> None:
        """Forget the account's count only, leaving the address's standing.

        The address's limit bounds how many accounts one client may try, so
        it must survive the successful login of any one of them.
        """
        await self._local_limiter(request).reset()

    def _local_limiter(self, request: ServerRequestInterface) -> LimiterInterface:
        """Return the limiter one account from one address counts under.

        The username is read the way the flow's other readers read it — off
        the request's security state, which the throttling listener parks it
        on while checking the passport — and an attempt that named no account
        counts under the empty one.
        """
        username = _state_attributes(request).get(SecurityRequestAttributes.LAST_USERNAME)
        named = username if isinstance(username, str) else ""
        return self._local_factory.create(self._hash(f"{named.lower()}-{_client_address(request)}"))

    def _hash(self, data: str) -> str:
        """Return the key ``data`` counts under: an 8-character HMAC prefix.

        A keyed digest, so the store a count lives in learns nothing about
        what it is counting; short, so the key stays cheap to keep and to
        compare; and prefixed with the secret, so two applications sharing a
        store never count under each other's keys.
        """
        digest = hmac.new(self._secret.encode(), data.encode(), sha256).digest()
        return base64.b64encode(digest).decode("ascii")[:8].translate(_KEY_ALPHABET)


def _client_address(request: ServerRequestInterface) -> str:
    """Return the address the server reported, or no address at all.

    Nothing about a request itself says where it came from — only the server
    that accepted it knows, and it says so among the environment parameters.
    A server that said nothing, or said something that is not an address,
    leaves the question unanswerable, which reads here as an address no
    network holds: the same attempt counts under one key, not under none.
    """
    client = request.get_server_params().get(_CLIENT)
    if isinstance(client, str) or not isinstance(client, Sequence):
        return ""

    first = client[0] if client else None

    return first if isinstance(first, str) else ""


def _state_attributes(request: ServerRequestInterface) -> Mapping[str, object]:
    """Return the attributes the request's security state carries.

    A request no stateful machinery ran for carries no state at all, and
    reads as carrying nothing — every lookup misses, which is the honest
    answer for a request the flow never touched: it named no account.
    """
    bag = request.get_attribute(SecurityRequestAttributes.STATE_BAG)
    if not isinstance(bag, MutableMapping):
        return {}
    return security_state_of(cast("MutableMapping[str, object]", bag)).attributes
