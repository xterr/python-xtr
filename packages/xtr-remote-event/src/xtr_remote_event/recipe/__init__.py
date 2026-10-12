"""This directory holds the package's recipe: its manifest.

The recipe is what *Use in an application* in the README lists, written as
data: the one bundle to list. There is nothing else to write — which consumer
answers for which source is declared beside each class, so no configuration
module, no environment variable and no ignore line belong to this package. An
application applies it with ``xtr-recipes recipes:sync``, which finds this
module through the ``xtr_recipes`` entry point.

Nothing is importable from here. The manifest is read as a file, so a recipe
is the same from a wheel as from a working tree.
"""

from __future__ import annotations

__all__: list[str] = []
