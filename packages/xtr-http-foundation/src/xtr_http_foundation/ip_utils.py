"""Placing an IP address inside a network, and hiding where it came from."""

from __future__ import annotations

import socket
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network
from typing import TYPE_CHECKING, Final, final

from .exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["IpUtils"]

_V4_BYTES: Final = 4
_V6_BYTES: Final = 16
_V4_BITS: Final = 32
_V6_BITS: Final = 128

# How an IPv6 address says it carries an IPv4 one: "::ffff:1.2.3.4" is the form in use,
# "::1.2.3.4" the one that came before it. What identifies an address as either is the
# bytes in front, so anonymizing one means dropping bytes from its four, not its sixteen.
_V4_MAPPED: Final = b"\x00" * 10 + b"\xff\xff"
_V4_COMPATIBLE: Final = b"\x00" * 12


def _as_ipv4(text: str) -> IPv4Address | None:
    """The IPv4 address ``text`` writes, or ``None`` when it writes none."""
    try:
        return IPv4Address(text)
    except ValueError:
        return None


def _as_ipv6(text: str) -> IPv6Address | None:
    """The IPv6 address ``text`` writes, or ``None`` when it writes none.

    A zone — the ``%eth0`` of ``fe80::1%eth0`` — names an interface of whichever host
    reads it, so the same text means a different address on the next machine. Nothing can
    be decided from one, and it is refused here rather than quietly dropped.
    """
    if "%" in text:
        return None
    try:
        return IPv6Address(text)
    except ValueError:
        return None


def _prefix_length(text: str, longest: int) -> int | None:
    """The CIDR prefix length ``text`` writes, or ``None`` when it writes none.

    Only ASCII digits count, so ``" 8"``, ``"+8"``, ``"8e0"`` and ``"8.5"`` name no prefix
    at all rather than the 8 a lenient reader would take from each of them — a network
    written wrongly must not silently become a wider one.
    """
    if not (text.isascii() and text.isdigit()):
        return None
    length = int(text)
    return length if length <= longest else None


def _masked(packed: bytes, mask: bytes) -> bytes:
    """``packed`` with every byte the mask does not keep zeroed."""
    return bytes(byte & keep for byte, keep in zip(packed, mask, strict=True))


@final
class IpUtils:
    """Where an address sits: in a network, in a private one, or hidden by its last bytes.

    A namespace rather than something to build — every answer here is a function of its
    arguments. Text that is not an address is no error for the checks: they answer about a
    request from a stranger, whose address is theirs to misspell, and an address nobody
    can read is one no network holds.
    """

    __slots__ = ()

    #: The networks an address in them can only be reached from inside this network.
    PRIVATE_SUBNETS: Final[tuple[str, ...]] = (
        "127.0.0.0/8",  # loopback
        "10.0.0.0/8",  # private use
        "192.168.0.0/16",  # private use
        "192.0.0.0/24",  # assigned to protocols rather than to hosts
        "192.0.2.0/24",  # reserved for documentation
        "198.51.100.0/24",  # reserved for documentation
        "203.0.113.0/24",  # reserved for documentation
        "172.16.0.0/12",  # private use
        "169.254.0.0/16",  # link local
        "192.88.99.0/24",  # 6to4 relay anycast, withdrawn
        "198.18.0.0/15",  # reserved for benchmarking
        "0.0.0.0/8",  # this network
        "240.0.0.0/4",  # reserved
        "100.64.0.0/10",  # shared address space, between a provider and its subscribers
        "224.0.0.0/4",  # multicast
        "::1/128",  # loopback
        "fc00::/7",  # unique local
        "fe80::/10",  # link local
        "::ffff:0:0/96",  # an IPv4 address written as an IPv6 one
        "::/128",  # unspecified
        "::/96",  # an IPv4 address written as an IPv6 one, in the earlier form
        "100::/64",  # discard only
        "2002::/16",  # 6to4
        "2001::/32",  # Teredo tunnelling
        "2001:db8::/32",  # reserved for documentation
        "2001:0002::/48",  # reserved for benchmarking
        "64:ff9b::/96",  # the well-known prefix translating IPv4 to IPv6
        "64:ff9b:1::/48",  # the same translation, for local use
        "ff00::/8",  # multicast
    )

    @staticmethod
    def check_ip(request_ip: str, ips: str | Sequence[str]) -> bool:
        """Whether ``request_ip`` falls in any of ``ips``.

        Args:
            request_ip: the address to place, written as IPv4 or IPv6.
            ips: a network in CIDR notation, a single address, or several of either.

        Returns:
            Whether any of them holds the address; ``False`` for text that is no address.
        """
        networks = (ips,) if isinstance(ips, str) else ips
        # More than one colon is what only an IPv6 address has — "::1" has two, while an
        # IPv4 address carrying a port would have one.
        check = IpUtils.check_ip6 if request_ip.count(":") > 1 else IpUtils.check_ip4
        return any(check(request_ip, network) for network in networks)

    @staticmethod
    def check_ip4(request_ip: str, ip: str) -> bool:
        """Whether ``request_ip`` falls in the IPv4 network or address ``ip``.

        Args:
            request_ip: the address to place, written as IPv4.
            ip: a network in CIDR notation, or a single address, which stands for itself.

        Returns:
            Whether the network holds the address; ``False`` when either is no IPv4 one.
        """
        address = _as_ipv4(request_ip)
        if address is None:
            return False
        network_text, separator, prefix_text = ip.partition("/")
        network_address = _as_ipv4(network_text)
        if network_address is None:
            return False
        prefix = _prefix_length(prefix_text, _V4_BITS) if separator else _V4_BITS
        if prefix is None:
            return False
        return address in IPv4Network((network_address, prefix), strict=False)

    @staticmethod
    def check_ip6(request_ip: str, ip: str) -> bool:
        """Whether ``request_ip`` falls in the IPv6 network or address ``ip``.

        Args:
            request_ip: the address to place, written as IPv6.
            ip: a network in CIDR notation, or a single address, which stands for itself.

        Returns:
            Whether the network holds the address; ``False`` when either is no IPv6 one.
        """
        address = _as_ipv6(request_ip)
        if address is None:
            return False
        network_text, separator, prefix_text = ip.partition("/")
        network_address = _as_ipv6(network_text)
        if network_address is None:
            return False
        prefix = _prefix_length(prefix_text, _V6_BITS) if separator else _V6_BITS
        if prefix is None:
            return False
        return address in IPv6Network((network_address, prefix), strict=False)

    @staticmethod
    def anonymize(ip: str, v4_bytes: int = 1, v6_bytes: int = 8) -> str:
        """``ip`` with its last bytes zeroed, so what is left no longer names one machine.

        Args:
            ip: the address to hide, bracketed or carrying a zone if that is how it came.
            v4_bytes: how many of an IPv4 address's four bytes to drop.
            v6_bytes: how many of an IPv6 address's sixteen bytes to drop.

        Returns:
            The address written as it arrived: bracketed if it was, and dotted where it
            carries an IPv4 one. A zone is never given back — it names an interface, which
            is as much a trace of who was asked as the bytes just dropped.

        Raises:
            InvalidArgumentError: when asked for fewer than no bytes, for more than the
                address has, or for text that is no address at all.
        """
        if v4_bytes < 0 or v6_bytes < 0:
            raise InvalidArgumentError("Cannot anonymize less than 0 bytes.")
        if v4_bytes > _V4_BYTES or v6_bytes > _V6_BYTES:
            raise InvalidArgumentError(
                "Cannot anonymize more than 4 bytes for IPv4 and 16 bytes for IPv6."
            )

        text = ip.partition("%")[0]
        wrapped = text.startswith("[") and text.endswith("]")
        if wrapped:
            text = text[1:-1]
        address: IPv4Address | IPv6Address | None = _as_ipv4(text) or _as_ipv6(text)
        if address is None:
            raise InvalidArgumentError(f'"{ip}" is not a valid IP address.')

        tail = b"\xff" * (_V4_BYTES - v4_bytes) + b"\x00" * v4_bytes
        packed = address.packed
        if isinstance(address, IPv4Address):
            anonymized = str(IPv4Address(_masked(packed, tail)))
        else:
            if packed.startswith(_V4_MAPPED):
                mask = _V4_MAPPED + tail
            elif packed.startswith(_V4_COMPATIBLE):
                mask = _V4_COMPATIBLE + tail
            else:
                mask = b"\xff" * (_V6_BYTES - v6_bytes) + b"\x00" * v6_bytes
            # `ipaddress` writes every group as hexadecimal, which would turn an address
            # carrying an IPv4 one into "::ffff:7bea:eb00" — the same bytes, no longer
            # recognisable as the address that went in. `inet_ntop` keeps the dotted form.
            anonymized = socket.inet_ntop(socket.AF_INET6, _masked(packed, mask))
        return f"[{anonymized}]" if wrapped else anonymized

    @staticmethod
    def is_private_ip(ip: str) -> bool:
        """Whether ``ip`` is an address only this network can reach.

        Args:
            ip: the address to place, written as IPv4 or IPv6.

        Returns:
            Whether it falls in any of :attr:`PRIVATE_SUBNETS`.

        Raises:
            InvalidArgumentError: when ``ip`` is not an address written plainly. This one
                refuses where the checks above answer, because its caller is asking
                whether an address may be reached out to, and text nobody can read is not
                an address that failed the question — it is a question nobody can answer.
        """
        if _as_ipv4(ip) is None and _as_ipv6(ip) is None:
            raise InvalidArgumentError(f'"{ip}" is not a valid IP address.')
        return IpUtils.check_ip(ip, IpUtils.PRIVATE_SUBNETS)
