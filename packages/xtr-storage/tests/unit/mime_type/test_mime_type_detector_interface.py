from __future__ import annotations

from xtr_storage.mime_type.extension_mime_type_detector import ExtensionMimeTypeDetector
from xtr_storage.mime_type.mime_type_detector_interface import MimeTypeDetectorInterface


def test_the_extension_detector_satisfies_the_interface() -> None:
    assert isinstance(ExtensionMimeTypeDetector(), MimeTypeDetectorInterface)


def test_an_object_missing_the_method_does_not_satisfy_the_interface() -> None:
    class WithoutDetect:
        pass

    assert not isinstance(WithoutDetect(), MimeTypeDetectorInterface)


def test_a_structural_match_satisfies_the_interface() -> None:
    class FixedDetector:
        def detect_from_path(self, path: str) -> str | None:
            del path
            return "application/octet-stream"

    assert isinstance(FixedDetector(), MimeTypeDetectorInterface)
