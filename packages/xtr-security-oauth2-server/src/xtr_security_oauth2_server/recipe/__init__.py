"""This directory holds the package's recipe: its manifest and its template.

The recipe is what *Use in an application* in the README lists, written as
data: the bundle to list, the configuration module naming the issuer, the key
material and the store, the environment variables that key material is read
from, the key files to keep out of the repository, and the steps only a person
can take — minting the key pair and putting a firewall in front of the
authorization endpoint among them — plus the routes file the endpoints are
arranged in. An application
applies it with ``xtr-recipes recipes:sync``, which finds this module through
the ``xtr_recipes`` entry point.

Nothing is importable from here. The manifest and the template are read as
files, so a recipe is the same from a wheel as from a working tree.
"""

from __future__ import annotations

__all__: list[str] = []
