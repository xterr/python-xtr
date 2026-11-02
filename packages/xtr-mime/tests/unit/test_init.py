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


def test_the_package_exports_the_headers() -> None:
    assert set(xtr_mime.header.__all__) <= set(xtr_mime.__all__)
    assert xtr_mime.Headers is xtr_mime.header.Headers


def test_the_package_exports_the_parts() -> None:
    assert set(xtr_mime.part.__all__) <= set(xtr_mime.__all__)
    assert xtr_mime.FormDataPart is xtr_mime.part.multipart.FormDataPart


def test_the_package_exports_dkim_signing() -> None:
    assert set(xtr_mime.crypto.__all__) <= set(xtr_mime.__all__)
    assert xtr_mime.DkimSigner is xtr_mime.crypto.DkimSigner


def test_the_package_exports_s_mime_signing_and_encryption() -> None:
    assert {"SMimeEncrypter", "SMimePart", "SMimeSigner"} <= set(xtr_mime.__all__)
    assert xtr_mime.SMimeSigner is xtr_mime.crypto.SMimeSigner
    assert xtr_mime.SMimePart is xtr_mime.part.SMimePart


def test_the_package_exports_the_messages() -> None:
    assert {
        "BodyRendererInterface",
        "DraftEmail",
        "Email",
        "Message",
        "MessageConverter",
        "RawMessage",
    } <= set(xtr_mime.__all__)


def test_the_package_exports_the_html_to_text_converters() -> None:
    assert set(xtr_mime.html_to_text_converter.__all__) <= set(xtr_mime.__all__)
    assert (
        xtr_mime.DefaultHtmlToTextConverter
        is xtr_mime.html_to_text_converter.DefaultHtmlToTextConverter
    )
