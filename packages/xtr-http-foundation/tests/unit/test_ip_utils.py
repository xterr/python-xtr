from __future__ import annotations

import re

import pytest

from xtr_http_foundation import IpUtils
from xtr_http_foundation.exception import InvalidArgumentError


def test_a_check_in_one_protocol_does_not_decide_the_other() -> None:
    assert IpUtils.check_ip6("192.168.52.1", "192.168.0.0/16") is False
    assert IpUtils.check_ip4("192.168.52.1", "192.168.0.0/16") is True
    assert IpUtils.check_ip4("2a01:198:603:0:396e:4789:8e99:890f", "2a01:198:603:0::/65") is False
    assert IpUtils.check_ip6("2a01:198:603:0:396e:4789:8e99:890f", "2a01:198:603:0::/65") is True


@pytest.mark.parametrize(
    ("matches", "request_ip", "ips"),
    [
        (True, "192.168.1.1", "192.168.1.1"),
        (True, "192.168.1.1", "192.168.1.1/1"),
        (True, "192.168.1.1", "192.168.1.0/24"),
        (False, "192.168.1.1", "1.2.3.4/1"),
        (False, "192.168.1.1", "192.168.1.1/33"),  # a prefix no IPv4 address has
        (True, "192.168.1.1", ["1.2.3.4/1", "192.168.1.0/24"]),
        (True, "192.168.1.1", ["192.168.1.0/24", "1.2.3.4/1"]),
        (False, "192.168.1.1", ["1.2.3.4/1", "4.3.2.1/1"]),
        (True, "1.2.3.4", "0.0.0.0/0"),
        (True, "1.2.3.4", "192.168.1.0/0"),
        (False, "1.2.3.4", "256.256.256/0"),  # no address to anchor the network on
        (False, "an_invalid_ip", "192.168.1.0/24"),
        (False, "", "1.2.3.4/1"),
        (False, "10.5.5.5", "10.0.0.0/8.5"),  # a prefix length is digits and nothing else
        (False, "10.5.5.5", "10.0.0.0/8e0"),
        (False, "10.5.5.5", "10.0.0.0/ 8"),
        (False, "10.5.5.5", "10.0.0.0/+8"),
        (False, "10.5.5.5", "10.0.0.0/-1"),
    ],
)
def test_check_ip_places_an_ipv4_address(
    matches: bool,
    request_ip: str,
    ips: str | list[str],
) -> None:
    assert IpUtils.check_ip(request_ip, ips) is matches


@pytest.mark.parametrize(
    ("matches", "request_ip", "ips"),
    [
        (True, "2a01:198:603:0:396e:4789:8e99:890f", "2a01:198:603:0::/65"),
        (False, "2a00:198:603:0:396e:4789:8e99:890f", "2a01:198:603:0::/65"),
        (False, "2a01:198:603:0:396e:4789:8e99:890f", "::1"),
        (True, "0:0:0:0:0:0:0:1", "::1"),
        (False, "0:0:603:0:396e:4789:8e99:0001", "::1"),
        (True, "0:0:603:0:396e:4789:8e99:0001", "::/0"),
        (True, "0:0:603:0:396e:4789:8e99:0001", "2a01:198:603:0::/0"),
        (True, "2a01:198:603:0:396e:4789:8e99:890f", ["::1", "2a01:198:603:0::/65"]),
        (True, "2a01:198:603:0:396e:4789:8e99:890f", ["2a01:198:603:0::/65", "::1"]),
        (False, "2a01:198:603:0:396e:4789:8e99:890f", ["::1", "1a01:198:603:0::/65"]),
        (False, "}__test|O:21:&quot;JDatabaseDriverMysqli&quot;:3:{s:2", "::1"),
        (False, "2a01:198:603:0:396e:4789:8e99:890f", "unknown"),
        (False, "", "::1"),
        (False, "127.0.0.1", "::1"),
        (False, "0.0.0.0/8", "::1"),
        (False, "::1", "127.0.0.1"),
        (False, "::1", "0.0.0.0/8"),
        (True, "::ffff:10.126.42.2", "::ffff:10.0.0.0/0"),
    ],
)
def test_check_ip_places_an_ipv6_address(
    matches: bool,
    request_ip: str,
    ips: str | list[str],
) -> None:
    assert IpUtils.check_ip(request_ip, ips) is matches


@pytest.mark.parametrize(
    ("request_ip", "network"),
    [
        pytest.param("192.168.20.13", "*", id="a wildcard is no network"),
        pytest.param("192.168.20.13", "0.0.0.0", id="an address with no prefix is itself"),
        pytest.param("0.0.0.0", "*", id="a wildcard matches nothing, not even the unspecified"),
    ],
)
def test_check_ip4_refuses_a_network_that_is_not_one(request_ip: str, network: str) -> None:
    assert IpUtils.check_ip4(request_ip, network) is False


@pytest.mark.parametrize(
    "network",
    [
        pytest.param("::1/129", id="a prefix no IPv6 address has"),
        pytest.param("::1/ 8", id="a prefix length is digits and nothing else"),
    ],
)
def test_check_ip6_refuses_a_prefix_that_is_not_one(network: str) -> None:
    assert IpUtils.check_ip6("::1", network) is False


@pytest.mark.parametrize(
    ("matches", "request_ip", "network"),
    [
        (True, "1.2.3.4", "0.0.0.0/0"),
        (True, "1.2.3.4", "192.168.1.0/0"),
        (False, "1.2.3.4", "256.256.256/0"),
    ],
)
def test_check_ip4_with_a_zero_prefix_asks_only_for_an_address(
    matches: bool,
    request_ip: str,
    network: str,
) -> None:
    assert IpUtils.check_ip4(request_ip, network) is matches


@pytest.mark.parametrize(
    ("ip", "expected"),
    [
        ("192.168.1.1", "192.168.1.0"),
        ("1.2.3.4", "1.2.3.0"),
        ("2a01:198:603:0:396e:4789:8e99:890f", "2a01:198:603::"),
        ("2a01:198:603:10:396e:4789:8e99:890f", "2a01:198:603:10::"),
        ("::1", "::"),
        ("0:0:0:0:0:0:0:1", "::"),
        ("1:0:0:0:0:0:0:1", "1::"),
        ("0:0:603:50:396e:4789:8e99:0001", "0:0:603:50::"),
        ("[0:0:603:50:396e:4789:8e99:0001]", "[0:0:603:50::]"),
        ("[2a01:198::3]", "[2a01:198::]"),
        ("::ffff:123.234.235.236", "::ffff:123.234.235.0"),  # an IPv4 address inside an IPv6 one
        ("::FFFF:123.234.235.236", "::ffff:123.234.235.0"),
        ("::ffff:7bea:ebec", "::ffff:123.234.235.0"),
        ("0000:0000:0000:0000:0000:ffff:7bea:ebec", "::ffff:123.234.235.0"),
        ("[::FFFF:123.234.235.236]", "[::ffff:123.234.235.0]"),
        ("::123.234.235.236", "::123.234.235.0"),  # the same, in the form that came before it
        ("::7bea:ebec", "::123.234.235.0"),
        ("::1:0:1", "::"),  # neither of those two: the whole tail goes
        ("0000:0000:0000:0000:0000:0001:0000:0001", "::"),
        ("fe80::1fc4:15d8:78db:2319%enp4s0", "fe80::"),  # the zone names an interface
    ],
)
def test_anonymize_drops_the_tail_of_an_address(ip: str, expected: str) -> None:
    assert IpUtils.anonymize(ip) == expected


@pytest.mark.parametrize(
    ("ip", "expected", "v4_bytes", "v6_bytes"),
    [
        ("192.168.1.1", "192.168.0.0", 2, 8),
        ("192.168.1.1", "192.0.0.0", 3, 8),
        ("192.168.1.1", "0.0.0.0", 4, 8),
        ("1.2.3.4", "1.2.3.0", 1, 8),
        ("1.2.3.4", "1.2.3.4", 0, 8),
        ("2a01:198:603:0:396e:4789:8e99:890f", "2a01:198:603:0:396e:4789:8e99:890f", 1, 0),
        ("2a01:198:603:0:396e:4789:8e99:890f", "2a01:198:603:0:396e:4789::", 1, 4),
        ("2a01:198:603:10:396e:4789:8e99:890f", "2a01:198:603:10:396e:4700::", 1, 5),
        ("2a01:198:603:10:396e:4789:8e99:890f", "2a00::", 1, 15),
        ("2a01:198:603:10:396e:4789:8e99:890f", "::", 1, 16),
        ("::1", "::", 1, 1),
        ("0:0:0:0:0:0:0:1", "::", 1, 1),
        ("1:0:0:0:0:0:0:1", "1::", 1, 1),
        ("0:0:603:50:396e:4789:8e99:0001", "0:0:603::", 1, 10),
        ("[0:0:603:50:396e:4789:8e99:0001]", "[::603:50:396e:4789:8e00:0]", 1, 3),
        ("[2a01:198::3]", "[2a01:198::]", 1, 2),
        ("::ffff:123.234.235.236", "::ffff:123.234.235.0", 1, 8),
        ("::123.234.235.236", "::123.234.0.0", 2, 8),
    ],
)
def test_anonymize_drops_as_many_bytes_as_it_is_asked_for(
    ip: str,
    expected: str,
    v4_bytes: int,
    v6_bytes: int,
) -> None:
    assert IpUtils.anonymize(ip, v4_bytes, v6_bytes) == expected


@pytest.mark.parametrize(("v4_bytes", "v6_bytes"), [(-1, 8), (1, -1)])
def test_anonymize_refuses_a_negative_number_of_bytes(v4_bytes: int, v6_bytes: int) -> None:
    with pytest.raises(InvalidArgumentError, match=r"^Cannot anonymize less than 0 bytes\.$"):
        _ = IpUtils.anonymize("anything", v4_bytes, v6_bytes)


@pytest.mark.parametrize(("v4_bytes", "v6_bytes"), [(5, 8), (1, 17)])
def test_anonymize_refuses_more_bytes_than_an_address_has(v4_bytes: int, v6_bytes: int) -> None:
    expected = r"^Cannot anonymize more than 4 bytes for IPv4 and 16 bytes for IPv6\.$"
    with pytest.raises(InvalidArgumentError, match=expected):
        _ = IpUtils.anonymize("anything", v4_bytes, v6_bytes)


def test_anonymize_refuses_an_address_that_is_not_one() -> None:
    with pytest.raises(InvalidArgumentError, match=r'^"anything" is not a valid IP address\.$'):
        _ = IpUtils.anonymize("anything")


@pytest.mark.parametrize(
    ("ip", "matches"),
    [
        ("127.0.0.1", True),
        ("10.0.0.1", True),
        ("192.168.0.1", True),
        ("192.0.2.1", True),
        ("198.51.100.1", True),
        ("203.0.113.1", True),
        ("172.16.0.1", True),
        ("169.254.0.1", True),
        ("198.18.0.1", True),
        ("0.0.0.1", True),
        ("240.0.0.1", True),
        ("100.64.0.1", True),
        ("::1", True),
        ("fc00::1", True),
        ("fe80::1", True),
        ("::ffff:0:1", True),
        ("fd00::1", True),
        ("::7f00:1", True),
        ("2002:7f00:1::", True),
        ("2001::1", True),
        ("2001:db8::1", True),
        ("2001:0002::1", True),
        ("64:ff9b::7f00:1", True),
        ("64:ff9b:1::7f00:1", True),
        ("192.0.0.1", True),
        ("192.0.0.8", True),
        ("192.88.99.1", True),
        ("224.0.0.1", True),
        ("239.255.255.250", True),
        ("233.1.1.1", True),
        ("100::1", True),
        ("ff02::1", True),
        ("ff05::1", True),
        ("ff0e::1", True),
        ("100:0:0:1::1", False),
        ("104.26.14.6", False),
        ("2606:4700:20::681a:e06", False),
        # Just past the boundary of the networks above, which pins their prefix lengths.
        ("100.128.0.1", False),
        ("198.20.0.1", False),
        ("2001:2:1::1", False),
    ],
)
def test_is_private_ip_tells_a_network_only_this_network_reaches(ip: str, matches: bool) -> None:
    assert IpUtils.is_private_ip(ip) is matches


@pytest.mark.parametrize(
    "ip",
    [
        pytest.param("2130706433", id="decimal"),
        pytest.param("0x7f000001", id="hexadecimal"),
        pytest.param("010.0.0.1", id="leading zero"),
        pytest.param("127.1", id="short form"),
        pytest.param("fe80::1%eth0", id="zone id"),
        pytest.param("not-an-ip", id="not an IP"),
        pytest.param("", id="empty string"),
    ],
)
def test_is_private_ip_refuses_an_address_that_is_not_canonical(ip: str) -> None:
    message = rf'^"{re.escape(ip)}" is not a valid IP address\.$'
    with pytest.raises(InvalidArgumentError, match=message):
        _ = IpUtils.is_private_ip(ip)


def test_the_private_networks_are_there_to_be_read() -> None:
    assert "127.0.0.0/8" in IpUtils.PRIVATE_SUBNETS
    assert "fc00::/7" in IpUtils.PRIVATE_SUBNETS
