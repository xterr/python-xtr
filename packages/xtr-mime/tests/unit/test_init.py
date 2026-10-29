"""The import package imports and lists the names it makes public."""

from __future__ import annotations

import xtr_mime


def test_the_package_imports_with_a_list_of_public_names() -> None:
    assert type(xtr_mime.__all__) is list


def test_the_package_exports_its_errors() -> None:
    assert {"MimeError", "RfcComplianceError"} <= set(xtr_mime.__all__)
    assert xtr_mime.RfcComplianceError is xtr_mime.exception.RfcComplianceError


def test_the_package_exports_mime_type_guessing() -> None:
    assert {
        "MagicMimeTypeGuesser",
        "MimeTypeGuesserInterface",
        "MimeTypes",
        "MimeTypesInterface",
    } <= set(xtr_mime.__all__)
