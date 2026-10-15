"""Testing a parser against the payloads its sender actually posts.

A parser is only as trustworthy as the captures it has been shown, and those
come from the sender: posted once, caught, kept. Keeping each in a file beside
the events it must become turns adding a case into adding two files — nothing
to register, nothing to write in the test — and leaves the payloads readable as
what they are, byte for byte, which is what a signature is made over.

The helpers build their requests with xtr-http-message, which comes with this
package, so there is nothing more to install.
"""

from __future__ import annotations

from ._parser_cases import assert_parses, parser_cases
from .parser_case import ParserCase

__all__ = ["ParserCase", "assert_parses", "parser_cases"]
