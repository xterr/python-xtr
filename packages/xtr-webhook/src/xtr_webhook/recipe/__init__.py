"""This directory holds the package's recipe: its manifest and its template.

The recipe is what *Use in an application* in the README lists, written as
data: the bundle to list, the configuration module to write, and the
environment variable the written module reads. An application applies it with
``xtr-recipes recipes:sync``, which finds this module through the
``xtr_recipes`` entry point.

The endpoint needs no step of its own: ``setup`` adds it, and the routes file
this recipe writes says where. Naming each sender's type is left to a person.

Nothing is importable from here. The manifest and the template are read as
files, so a recipe is the same from a wheel as from a working tree.
"""

from __future__ import annotations

__all__: list[str] = []
