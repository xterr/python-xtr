from __future__ import annotations

import re

from xtr_web_profiler.csp import NonceGenerator


def test_every_nonce_is_fresh_and_128_bits_of_hex() -> None:
    generator = NonceGenerator()

    first, second = generator.generate(), generator.generate()

    assert re.fullmatch(r"[0-9a-f]{32}", first)
    assert first != second
