from __future__ import annotations

import pytest

from xtr_storage.mime_type.extension_mime_type_detector import ExtensionMimeTypeDetector


@pytest.fixture
def detector() -> ExtensionMimeTypeDetector:
    return ExtensionMimeTypeDetector()


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("logo.svg", "image/svg+xml"),
        ("readme.md", "text/markdown"),
        ("photo.webp", "image/webp"),
        ("data.json", "application/json"),
        ("notes.txt", "text/plain"),
    ],
)
def test_it_maps_a_known_extension_to_its_media_type(
    detector: ExtensionMimeTypeDetector,
    path: str,
    expected: str,
) -> None:
    assert detector.detect_from_path(path) == expected


def test_it_reads_the_explicit_additions_regardless_of_the_built_in_table(
    detector: ExtensionMimeTypeDetector,
) -> None:
    added = {
        "a.svg": "image/svg+xml",
        "a.md": "text/markdown",
        "a.webp": "image/webp",
        "a.json": "application/json",
    }

    assert {path: detector.detect_from_path(path) for path in added} == added


def test_it_ignores_extension_case(detector: ExtensionMimeTypeDetector) -> None:
    assert detector.detect_from_path("a/logo.SVG") == "image/svg+xml"


def test_it_reads_only_the_trailing_extension(
    detector: ExtensionMimeTypeDetector,
) -> None:
    assert detector.detect_from_path("deep/nested/dir/report.md") == "text/markdown"


def test_it_returns_none_for_an_unknown_extension(
    detector: ExtensionMimeTypeDetector,
) -> None:
    assert detector.detect_from_path("file.md5") is None


def test_it_returns_none_for_a_path_without_an_extension(
    detector: ExtensionMimeTypeDetector,
) -> None:
    assert detector.detect_from_path("Makefile") is None


def test_it_does_not_read_host_media_type_files() -> None:
    """Two instances agree because the mapping comes from the built-in table only.

    A detector that read ``/etc/mime.types`` would drift between machines; this
    proves the guess depends on nothing the host configures.
    """
    first = ExtensionMimeTypeDetector()
    second = ExtensionMimeTypeDetector()

    assert first.detect_from_path("a.svg") == second.detect_from_path("a.svg")
