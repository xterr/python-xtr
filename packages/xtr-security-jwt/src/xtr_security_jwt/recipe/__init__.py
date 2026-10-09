"""This directory holds the package's recipe: its manifest and its template.

The recipe is what *Use in an application* in the README lists, written as
data: the bundle to list, the configuration module pointing the signing key at
a file, the environment variable naming that file, the key files to keep out of
the repository, and the steps only a person can take — minting a development key
among them. An application applies it with ``xtr-recipes recipes:sync``, which
finds this module through the ``xtr_recipes`` entry point.

Nothing is importable from here. The manifest and the template are read as
files, so a recipe is the same from a wheel as from a working tree.
"""

from __future__ import annotations

__all__: list[str] = []
