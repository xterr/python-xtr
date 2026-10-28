"""The import package imports and lists the names it makes public."""

from __future__ import annotations

import xtr_mime


def test_the_package_imports_with_a_list_of_public_names() -> None:
    assert type(xtr_mime.__all__) is list
