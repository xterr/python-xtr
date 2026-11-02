"""This directory holds the package's recipe: its manifest.

The recipe is what *Use in an application* in the README lists, written as
data: the step only a person can take — enabling the delayed-message exchange
plugin on the broker, or turning it off on the DSN. An application applies it
with ``xtr-recipes recipes:sync``, which finds this module through the
``xtr_recipes`` entry point.

Nothing is importable from here. The manifest is read as a file, so a recipe
is the same from a wheel as from a working tree.
"""

from __future__ import annotations

__all__: list[str] = []
