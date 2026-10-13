from __future__ import annotations

import pytest

from xtr_http_client.exception import InvalidArgumentError
from xtr_http_client.internal.peer_fingerprint import normalize_peer_fingerprint

_MD5 = "d41d8cd98f00b204e9800998ecf8427e"
_SHA1 = "da39a3ee5e6b4b0d3255bfef95601890afd80709"
_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
_PIN = "AAAABBBBCCCCDDDDEEEEFFFFGGGGHHHHIIIIJJJJKKKK"


@pytest.mark.parametrize(
    ("fingerprint", "expected"),
    [
        (_MD5, {"md5": _MD5}),
        (_SHA1, {"sha1": _SHA1}),
        (_SHA256, {"sha256": _SHA256}),
        (_PIN, {"pin-sha256": (_PIN,)}),
    ],
)
def test_the_algorithm_is_told_from_the_length_of_the_digest(
    fingerprint: str,
    expected: dict[str, object],
) -> None:
    assert normalize_peer_fingerprint(fingerprint) == expected


def test_the_colons_a_digest_is_usually_written_with_are_dropped() -> None:
    written = ":".join(_MD5[i : i + 2] for i in range(0, len(_MD5), 2))

    assert normalize_peer_fingerprint(written) == {"md5": _MD5}
    assert normalize_peer_fingerprint({"sha1": f"{_SHA1[:4]}:{_SHA1[4:]}"}) == {"sha1": _SHA1}


def test_a_pin_is_always_a_list_of_pins() -> None:
    assert normalize_peer_fingerprint({"pin-sha256": _PIN}) == {"pin-sha256": (_PIN,)}
    assert normalize_peer_fingerprint({"pin-sha256": [_PIN, _PIN]}) == {
        "pin-sha256": (_PIN, _PIN),
    }


def test_a_digest_of_a_length_no_algorithm_has_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = normalize_peer_fingerprint("foo")

    assert str(raised.value) == 'Cannot auto-detect fingerprint algorithm for "foo".'


def test_a_fingerprint_that_is_neither_a_digest_nor_a_mapping_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = normalize_peer_fingerprint(object())

    assert str(raised.value) == (
        'Option "peer_fingerprint" must be a string or a mapping, "object" given.'
    )
