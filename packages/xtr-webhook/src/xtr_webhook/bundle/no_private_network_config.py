"""What the outbound guard refuses, and the few addresses it still allows."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import final

from xtr_webhook.exception import InvalidArgumentError

__all__ = ["NoPrivateNetworkConfig"]


@final
@dataclass(frozen=True, slots=True)
class NoPrivateNetworkConfig:
    """Whether the client webhooks are sent through refuses to deliver into a private network.

    Off by default: a receiver on this network is a legitimate setup until the
    application says otherwise. Turned on, it wraps that client in
    :class:`~xtr_http_client.NoPrivateNetworkHttpClient`, which checks what
    every destination *resolves to* before anything is sent.

    Attributes:
        enabled: Whether outgoing webhooks are vetted at all.
        subnets: The networks to refuse, in CIDR notation, replacing the
            default. ``None`` refuses every address that is not globally
            routable — loopback, private, link-local, carrier-grade NAT,
            unique-local, multicast, reserved and unspecified alike.
        allow_list: Networks or single addresses exempt from the refusal.
            Addresses only, never hostnames: the check runs on resolved
            addresses, and a name could point anywhere by the time it is used.
    """

    enabled: bool = False
    subnets: tuple[str, ...] | None = None
    allow_list: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Refuse an entry that names no network, and tuning on a guard that is off.

        The second check exists because this configuration cannot imply
        consent: naming subnets does not turn the guard on, so accepting them
        while it is off would leave an application believing it is protected.

        Raises:
            InvalidArgumentError: When ``subnets`` or ``allow_list`` is given
                while ``enabled`` is ``False``, or an entry is not an IP
                network or address.
        """
        if not self.enabled and (self.subnets is not None or self.allow_list):
            raise InvalidArgumentError(
                "no_private_network.subnets and allow_list take effect only with enabled=True.",
            )
        for entry in (*(self.subnets or ()), *self.allow_list):
            try:
                _ = ipaddress.ip_network(entry, strict=False)
            except ValueError as error:
                raise InvalidArgumentError(f'"{entry}" is not an IP network.') from error
