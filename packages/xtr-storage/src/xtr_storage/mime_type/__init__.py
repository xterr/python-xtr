"""Guessing a file's media type from its path, without reading its contents."""

from __future__ import annotations

from .extension_mime_type_detector import ExtensionMimeTypeDetector
from .mime_type_detector_interface import MimeTypeDetectorInterface

__all__ = ["ExtensionMimeTypeDetector", "MimeTypeDetectorInterface"]
