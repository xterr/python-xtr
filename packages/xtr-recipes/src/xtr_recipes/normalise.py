"""One spelling of a distribution name, shared by everything that compares them."""

from __future__ import annotations

import re

__all__ = ["normalise"]

# PEP 503 normalisation: a run of dashes, underscores or dots is one separator,
# so a package named on a command line matches the dependency list however it
# was spelled.
_SEPARATORS = re.compile(r"[-_.]+")


def normalise(name: str) -> str:
    """Return a distribution name as a dependency list spells it."""
    return _SEPARATORS.sub("-", name.strip()).lower()
