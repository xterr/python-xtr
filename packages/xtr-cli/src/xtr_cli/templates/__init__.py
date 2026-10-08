"""The templates this tool ships, one directory each, read as package data.

A real package so the build carries every ``template.toml`` and ``*.tmpl``
file beside it in the wheel. Nothing here is imported or run: the files are
templates, named ``*.tmpl`` so they are never linted or type-checked as code.
"""

from __future__ import annotations

__all__: list[str] = []
