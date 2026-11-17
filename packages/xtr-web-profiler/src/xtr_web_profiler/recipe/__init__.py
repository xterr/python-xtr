"""This directory holds the package's recipe: its manifest and the file it writes.

The recipe is what *Use in an application* in the README lists, written as
data: the bundle to list for development, and the routes file of the
development environment that serves the toolbar and the profiler's pages. An
application applies it with ``xtr-recipes recipes:sync``, which finds this
module through the ``xtr_recipes`` entry point.

Nothing is importable from here. The manifest is read as a file, so a recipe
is the same from a wheel as from a working tree.
"""

from __future__ import annotations

__all__: list[str] = []
